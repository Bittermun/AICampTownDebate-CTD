# TASK-006 output - see CODEX_QUEUE.md
import re
from urllib.parse import urlparse


def _is_sqlite(conn) -> bool:
    return conn.__class__.__module__.startswith("sqlite3")


def _placeholder(conn) -> str:
    return "?" if _is_sqlite(conn) else "%s"


def _row_to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    return None


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "agent"


def register_agent(conn, model_id: str, provider_base_url: str, api_key: str = None) -> str:
    netloc = urlparse(provider_base_url).netloc or provider_base_url
    agent_id = _slugify(f"{model_id}_{netloc}")
    provider_config_id = agent_id
    p = _placeholder(conn)

    conn.execute(
        f"""
        INSERT INTO provider_configs (id, base_url, api_key, model_id)
        VALUES ({p}, {p}, {p}, {p})
        ON CONFLICT(id) DO UPDATE SET
            base_url = excluded.base_url,
            api_key = excluded.api_key,
            model_id = excluded.model_id
        """,
        (provider_config_id, provider_base_url, api_key, model_id),
    )

    conn.execute(
        f"""
        INSERT INTO agents (id, name, provider_config_id)
        VALUES ({p}, {p}, {p})
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            provider_config_id = excluded.provider_config_id
        """,
        (agent_id, model_id, provider_config_id),
    )
    return agent_id


def get_or_create_agent(conn, model_id: str, provider_base_url: str, api_key: str = None) -> dict:
    agent_id = register_agent(conn, model_id, provider_base_url, api_key)
    p = _placeholder(conn)
    row = conn.execute(f"SELECT * FROM agents WHERE id = {p}", (agent_id,)).fetchone()
    return _row_to_dict(row)


def apply_patch_notification(conn, agent_id: str, current_patch: str) -> str | None:
    p = _placeholder(conn)
    row = conn.execute(
        f"SELECT last_patch_applied FROM agents WHERE id = {p}",
        (agent_id,),
    ).fetchone()
    state = _row_to_dict(row)
    if not state:
        return None

    last_patch = state.get("last_patch_applied")
    if last_patch == current_patch:
        return None

    if last_patch:
        rows = conn.execute(
            f"""
            SELECT version, description
            FROM patches
            WHERE applied_at > COALESCE((SELECT applied_at FROM patches WHERE version = {p}), '')
              AND applied_at <= COALESCE((SELECT applied_at FROM patches WHERE version = {p}), applied_at)
            ORDER BY applied_at
            """,
            (last_patch, current_patch),
        ).fetchall()
    else:
        rows = conn.execute(
            f"""
            SELECT version, description
            FROM patches
            WHERE applied_at <= COALESCE((SELECT applied_at FROM patches WHERE version = {p}), applied_at)
            ORDER BY applied_at
            """,
            (current_patch,),
        ).fetchall()

    notes = []
    for patch_row in rows:
        item = _row_to_dict(patch_row)
        if item:
            notes.append(item.get("description", ""))
    summary = " | ".join([n for n in notes if n]) or "Rule/economy updates applied."

    from_version = last_patch or "none"
    return f"PATCH NOTES since your last run ({from_version} -> {current_patch}): {summary}"
