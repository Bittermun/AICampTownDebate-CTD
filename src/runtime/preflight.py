"""Runtime preflight checks for experiment validity."""
from dataclasses import dataclass
from typing import Iterable, List

from ..models.provider_backend import ProviderBackend, ProviderConfig


@dataclass
class ModelCheckResult:
    label: str
    configured_model: str
    resolved_model: str
    backend: str
    available: bool
    detail: str = ""


def normalize_model_path(model: str) -> str:
    """Normalize model path for provider backend."""
    if model == "stub":
        return "stub"
    if ":" in model:
        prefix, rest = model.split(":", 1)
        if prefix in {"ollama", "vllm", "openai"} and rest:
            return rest
    return model


def backend_from_model_path(model_path: str) -> str:
    if model_path == "stub" or model_path.startswith("stub:"):
        return "stub"
    return "provider"


def _check_provider(model_path: str) -> tuple[bool, str]:
    backend = ProviderBackend(ProviderConfig(model=model_path))
    if not backend.is_available():
        return False, "Provider endpoint unavailable"
    available_models = backend.list_models()
    if available_models and model_path not in available_models:
        return False, f"Provider model '{model_path}' not exposed by /v1/models"
    return True, "Provider endpoint available"


def check_model(label: str, configured_model: str) -> ModelCheckResult:
    resolved = normalize_model_path(configured_model)
    backend = backend_from_model_path(resolved)

    if backend == "stub":
        return ModelCheckResult(label, configured_model, resolved, backend, True, "Explicit stub model")

    ok, detail = _check_provider(resolved)
    return ModelCheckResult(label, configured_model, resolved, backend, ok, detail)


def run_preflight(
    model_specs: Iterable[tuple[str, str]],
    allow_stub: bool = False,
    allow_backend_fallback: bool = False,
) -> List[ModelCheckResult]:
    """Run runtime checks. Raises RuntimeError when strict checks fail."""
    results = [check_model(label, model) for label, model in model_specs]

    failures: list[str] = []
    for r in results:
        if r.backend == "stub" and not allow_stub:
            failures.append(f"{r.label}: stub backend blocked in strict mode")
            continue
        if not r.available and not allow_backend_fallback:
            failures.append(f"{r.label}: {r.detail}")

    if failures:
        joined = "\n".join(f"- {f}" for f in failures)
        raise RuntimeError(
            "Preflight failed. Refusing to run experiment with invalid runtime conditions:\n"
            f"{joined}\n"
            "Use --allow-stub to permit fallback/stub runs."
        )

    return results


def print_preflight(results: List[ModelCheckResult]) -> None:
    print("\nRuntime preflight:")
    for r in results:
        status = "OK" if r.available else "FAIL"
        print(f"  [{status}] {r.label}: {r.resolved_model} ({r.backend}) - {r.detail}")
