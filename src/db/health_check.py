# TASK-007 output - see CODEX_QUEUE.md
from datetime import datetime

import requests

from src.models.provider_backend import ProviderConfig


def _is_sqlite(conn) -> bool:
    return conn.__class__.__module__.startswith("sqlite3")


def _placeholder(conn) -> str:
    return "?" if _is_sqlite(conn) else "%s"


def _update_last_health_ok(conn, config: ProviderConfig) -> None:
    p = _placeholder(conn)
    conn.execute(
        f"""
        UPDATE provider_configs
        SET last_health_ok = {p}
        WHERE base_url = {p} AND model_id = {p}
        """,
        (datetime.utcnow(), config.base_url, config.model),
    )


def check_provider(config: ProviderConfig, conn=None) -> bool:
    base_url = config.base_url.rstrip("/")
    url = f"{base_url}/v1/models"
    headers = {}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    try:
        resp = requests.get(url, headers=headers, timeout=5)
    except Exception as exc:
        print(f"[health] FAIL {exc}")
        return False

    if resp.status_code != 200:
        print(f"[health] FAIL status={resp.status_code}")
        return False

    try:
        payload = resp.json()
    except Exception:
        print("[health] FAIL invalid_json")
        return False

    models = payload.get("data", []) if isinstance(payload, dict) else []
    if not isinstance(models, list) or len(models) == 0:
        print("[health] FAIL no_models")
        return False

    first = models[0] if isinstance(models[0], dict) else {}
    model_id = first.get("id") if isinstance(first, dict) else None
    if not model_id:
        model_id = config.model

    if conn is not None:
        _update_last_health_ok(conn, config)

    print(f"[health] OK {model_id}")
    return True
