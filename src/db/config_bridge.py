# TASK-011 output - see CODEX_QUEUE.md
import os

import yaml

from .agent_registry import register_agent


def _normalize_model_id(raw_model: str) -> str:
    model = (raw_model or "").strip()
    if model.startswith("openai:"):
        return model[len("openai:") :]
    return model


def register_from_yaml(conn, config_path: str) -> list[str]:
    base_url = os.getenv("OPENAI_COMPAT_BASE_URL")
    if not base_url:
        raise ValueError("OPENAI_COMPAT_BASE_URL is required")

    with open(config_path, "r", encoding="utf-8-sig") as f:
        payload = yaml.safe_load(f) or {}

    models = payload.get("models", {})
    debaters = models.get("debaters", [])
    judges = models.get("judges", [])

    agent_ids = []
    for spec in [*debaters, *judges]:
        if not isinstance(spec, dict):
            continue
        model_id = _normalize_model_id(str(spec.get("model", "")))
        if not model_id:
            continue
        agent_ids.append(register_agent(conn, model_id, base_url))
    return agent_ids
