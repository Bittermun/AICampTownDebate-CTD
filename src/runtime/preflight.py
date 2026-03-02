"""Runtime preflight checks for experiment validity."""
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

from ..models.ollama_backend import get_backend, OllamaConfig
from ..models.openai_compat_backend import OpenAICompatBackend, OpenAICompatConfig
from ..models.vllm_backend import VLLMBackend, VLLMConfig


@dataclass
class ModelCheckResult:
    label: str
    configured_model: str
    resolved_model: str
    backend: str
    available: bool
    detail: str = ""


def normalize_model_path(model: str) -> str:
    """Normalize model path while preserving explicit backend prefixes."""
    if model == "stub":
        return "stub"
    if ":" in model:
        prefix = model.split(":", 1)[0]
        if prefix in {"ollama", "vllm", "openai", "stub"}:
            return model
    return f"ollama:{model}"


def backend_from_model_path(model_path: str) -> str:
    if model_path.startswith("ollama:"):
        return "ollama"
    if model_path.startswith("vllm:"):
        return "vllm"
    if model_path.startswith("openai:"):
        return "openai_compat"
    if model_path == "stub" or model_path.startswith("stub:"):
        return "stub"
    return "llama_cpp"


def _check_ollama(model_path: str) -> tuple[bool, str]:
    model_name = model_path.split(":", 1)[1]
    backend = get_backend(OllamaConfig(model=model_name))
    if not backend.is_available():
        return False, "Ollama server unavailable"
    models = backend.list_models()
    if models and model_name not in models:
        return False, f"Ollama model '{model_name}' not found (run: ollama pull {model_name})"
    return True, "Ollama model available"


def _check_vllm(model_path: str) -> tuple[bool, str]:
    model_name = model_path.split(":", 1)[1]
    backend = VLLMBackend(VLLMConfig(model=model_name))
    if not backend.is_available():
        return False, "vLLM server unavailable"
    available_models = backend.list_models()
    if available_models and model_name not in available_models:
        return False, f"vLLM model '{model_name}' not exposed by /v1/models"
    return True, "vLLM server available"


def _check_llama_cpp(model_path: str) -> tuple[bool, str]:
    path = Path(model_path)
    if not path.exists():
        return False, f"llama.cpp model path not found: {model_path}"
    return True, "llama.cpp model path exists"


def _check_openai_compat(model_path: str) -> tuple[bool, str]:
    model_name = model_path.split(":", 1)[1]
    backend = OpenAICompatBackend(OpenAICompatConfig(model=model_name))
    if not backend.is_available():
        return False, "OpenAI-compatible endpoint unavailable"
    available_models = backend.list_models()
    if available_models and model_name not in available_models:
        return False, f"OpenAI-compatible model '{model_name}' not exposed by /v1/models"
    return True, "OpenAI-compatible endpoint available"


def check_model(label: str, configured_model: str) -> ModelCheckResult:
    resolved = normalize_model_path(configured_model)
    backend = backend_from_model_path(resolved)

    if backend == "stub":
        return ModelCheckResult(label, configured_model, resolved, backend, True, "Explicit stub model")
    if backend == "ollama":
        ok, detail = _check_ollama(resolved)
        return ModelCheckResult(label, configured_model, resolved, backend, ok, detail)
    if backend == "vllm":
        ok, detail = _check_vllm(resolved)
        return ModelCheckResult(label, configured_model, resolved, backend, ok, detail)
    if backend == "openai_compat":
        ok, detail = _check_openai_compat(resolved)
        return ModelCheckResult(label, configured_model, resolved, backend, ok, detail)

    ok, detail = _check_llama_cpp(resolved)
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
