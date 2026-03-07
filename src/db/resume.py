# TASK-009 output - see CODEX_QUEUE.md
from __future__ import annotations

from datetime import datetime, timedelta


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


def _fetch_one(conn, sql: str, params=()):
    if _is_sqlite(conn):
        return conn.execute(sql, params).fetchone()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        cur.close()


def _execute_write(conn, sql: str, params=()) -> int:
    if _is_sqlite(conn):
        cur = conn.execute(sql, params)
        return cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return cur.rowcount if cur.rowcount is not None and cur.rowcount >= 0 else 0
    finally:
        cur.close()


def get_resumable_tournament(conn, tournament_id: str) -> dict | None:
    sql = (
        f"SELECT * FROM tournaments WHERE id={_param(conn)} "
        f"AND status IN ({_param(conn)}, {_param(conn)})"
    )
    row = _fetch_one(conn, sql, (tournament_id, "running", "failed"))
    return _row_to_dict(row)


def get_resume_point(conn, tournament_id: str) -> int:
    sql = (
        f"SELECT MAX(round_number) AS last_round FROM tournament_rounds "
        f"WHERE tournament_id={_param(conn)} AND status={_param(conn)}"
    )
    row = _fetch_one(conn, sql, (tournament_id, "completed"))
    if row is None:
        return 1
    last_round = row["last_round"] if hasattr(row, "__getitem__") else None
    if last_round is None:
        return 1
    return int(last_round) + 1


def mark_stale_rounds_dead(conn, tournament_id: str, timeout_minutes: int = 5) -> int:
    cutoff = datetime.utcnow() - timedelta(minutes=timeout_minutes)
    cutoff_value = cutoff.strftime("%Y-%m-%d %H:%M:%S") if _is_sqlite(conn) else cutoff
    sql = (
        f"UPDATE tournament_rounds SET status={_param(conn)} "
        f"WHERE tournament_id={_param(conn)} AND status={_param(conn)} "
        f"AND created_at < {_param(conn)}"
    )
    return _execute_write(conn, sql, ("dead", tournament_id, "running", cutoff_value))
