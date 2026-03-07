# TASK-003 output - see CODEX_QUEUE.md
from __future__ import annotations


def _is_sqlite(conn) -> bool:
    return conn.__class__.__module__.startswith("sqlite3")


def _param(conn) -> str:
    return "?" if _is_sqlite(conn) else "%s"


def _row_to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(row)


def _execute_write(conn, sql: str, params=()) -> None:
    if _is_sqlite(conn):
        conn.execute(sql, params)
        return
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
    finally:
        cur.close()


def _fetch_one(conn, sql: str, params=()):
    if _is_sqlite(conn):
        return conn.execute(sql, params).fetchone()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        cur.close()


def upsert_agent(conn, id, name, provider_config_id, **kwargs) -> None:
    fields = {
        "id": id,
        "name": name,
        "provider_config_id": provider_config_id,
        **kwargs,
    }
    cols = list(fields.keys())
    placeholders = ", ".join([_param(conn)] * len(cols))
    updates = ", ".join(f"{col}=excluded.{col}" for col in cols if col != "id")
    sql = (
        f"INSERT INTO agents ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(id) DO UPDATE SET {updates}"
    )
    _execute_write(conn, sql, tuple(fields[col] for col in cols))


def get_agent(conn, id) -> dict | None:
    sql = f"SELECT * FROM agents WHERE id={_param(conn)}"
    return _row_to_dict(_fetch_one(conn, sql, (id,)))


def update_agent_state(conn, id, **fields) -> None:
    if not fields:
        return
    set_clause = ", ".join(f"{col}={_param(conn)}" for col in fields)
    sql = f"UPDATE agents SET {set_clause} WHERE id={_param(conn)}"
    params = tuple(fields[col] for col in fields) + (id,)
    _execute_write(conn, sql, params)


def create_tournament(conn, id, config_json, patch_version, seed) -> None:
    sql = (
        f"INSERT INTO tournaments (id, config_json, patch_version, seed) "
        f"VALUES ({_param(conn)}, {_param(conn)}, {_param(conn)}, {_param(conn)})"
    )
    _execute_write(conn, sql, (id, config_json, patch_version, seed))


def update_tournament_status(conn, id, status, **kwargs) -> None:
    fields = {"status": status, **kwargs}
    set_clause = ", ".join(f"{col}={_param(conn)}" for col in fields)
    sql = f"UPDATE tournaments SET {set_clause} WHERE id={_param(conn)}"
    params = tuple(fields[col] for col in fields) + (id,)
    _execute_write(conn, sql, params)


def get_tournament(conn, id) -> dict | None:
    sql = f"SELECT * FROM tournaments WHERE id={_param(conn)}"
    return _row_to_dict(_fetch_one(conn, sql, (id,)))


def insert_round(conn, idempotency_key, tournament_id, round_number, agent_id, patch_version) -> None:
    sql = (
        "INSERT INTO tournament_rounds "
        f"(idempotency_key, tournament_id, round_number, agent_id, patch_version) "
        f"VALUES ({_param(conn)}, {_param(conn)}, {_param(conn)}, {_param(conn)}, {_param(conn)})"
    )
    _execute_write(conn, sql, (idempotency_key, tournament_id, round_number, agent_id, patch_version))


def update_round(conn, idempotency_key, status, **kwargs) -> None:
    fields = {"status": status, **kwargs}
    set_clause = ", ".join(f"{col}={_param(conn)}" for col in fields)
    sql = f"UPDATE tournament_rounds SET {set_clause} WHERE idempotency_key={_param(conn)}"
    params = tuple(fields[col] for col in fields) + (idempotency_key,)
    _execute_write(conn, sql, params)


def get_last_completed_round(conn, tournament_id) -> dict | None:
    sql = (
        f"SELECT * FROM tournament_rounds WHERE tournament_id={_param(conn)} "
        f"AND status={_param(conn)} ORDER BY round_number DESC LIMIT 1"
    )
    return _row_to_dict(_fetch_one(conn, sql, (tournament_id, "completed")))


def add_participant(conn, tournament_id, agent_id, role, starting_balance) -> None:
    sql = (
        "INSERT INTO tournament_participants "
        f"(tournament_id, agent_id, role, starting_balance) VALUES ({_param(conn)}, {_param(conn)}, {_param(conn)}, {_param(conn)})"
    )
    _execute_write(conn, sql, (tournament_id, agent_id, role, starting_balance))


def set_participant_final_balance(conn, tournament_id, agent_id, final_balance) -> None:
    sql = (
        f"UPDATE tournament_participants SET final_balance={_param(conn)} "
        f"WHERE tournament_id={_param(conn)} AND agent_id={_param(conn)}"
    )
    _execute_write(conn, sql, (final_balance, tournament_id, agent_id))


def save_snapshot(conn, agent_id, tournament_id, round_number, patch_version, state_json) -> None:
    sql = (
        "INSERT INTO agent_state_snapshots "
        f"(agent_id, tournament_id, round_number, patch_version, state_json) VALUES ({_param(conn)}, {_param(conn)}, {_param(conn)}, {_param(conn)}, {_param(conn)})"
    )
    _execute_write(conn, sql, (agent_id, tournament_id, round_number, patch_version, state_json))
