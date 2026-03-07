# TASK-010 output - see CODEX_QUEUE.md
from __future__ import annotations

import json
from typing import Any


def _is_sqlite(conn) -> bool:
    return conn.__class__.__module__.startswith("sqlite3")


def _param(conn) -> str:
    return "?" if _is_sqlite(conn) else "%s"


def _row_to_dict(row, columns: list[str] | None = None) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    if columns:
        return {col: row[idx] for idx, col in enumerate(columns)}
    return dict(row)


def _fetch_all(conn, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    if _is_sqlite(conn):
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(row) for row in rows]

    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description] if cur.description else []
        return [_row_to_dict(row, columns) for row in rows]
    finally:
        cur.close()


def _fetch_one(conn, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    if _is_sqlite(conn):
        row = conn.execute(sql, params).fetchone()
        return _row_to_dict(row) if row is not None else None

    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        row = cur.fetchone()
        if row is None:
            return None
        columns = [desc[0] for desc in cur.description] if cur.description else []
        return _row_to_dict(row, columns)
    finally:
        cur.close()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_leaderboard(conn, limit: int = 20) -> list[dict]:
    sql = (
        "SELECT id, name, career_wins, career_losses, career_roi, last_active_at "
        "FROM agents "
        "ORDER BY career_roi DESC, career_wins DESC, id ASC "
        f"LIMIT {_param(conn)}"
    )
    rows = _fetch_all(conn, sql, (_safe_int(limit, 20),))
    return [
        {
            "id": row.get("id"),
            "name": row.get("name"),
            "career_wins": _safe_int(row.get("career_wins"), 0),
            "career_losses": _safe_int(row.get("career_losses"), 0),
            "career_roi": _safe_float(row.get("career_roi")),
            "last_active_at": row.get("last_active_at"),
        }
        for row in rows
    ]


def get_agent_history(conn, agent_id: str, limit: int = 50) -> list[dict]:
    sql = (
        "SELECT tournament_id, round_number, roi, judge_scores, patch_version, completed_at "
        "FROM tournament_rounds "
        f"WHERE agent_id={_param(conn)} AND status={_param(conn)} "
        "ORDER BY completed_at DESC, round_number DESC "
        f"LIMIT {_param(conn)}"
    )
    rows = _fetch_all(conn, sql, (agent_id, "completed", _safe_int(limit, 50)))
    history: list[dict[str, Any]] = []
    for row in rows:
        judge_scores = row.get("judge_scores")
        if isinstance(judge_scores, str):
            try:
                judge_scores = json.loads(judge_scores)
            except json.JSONDecodeError:
                pass
        history.append(
            {
                "tournament_id": row.get("tournament_id"),
                "round_number": _safe_int(row.get("round_number"), 0),
                "roi": _safe_float(row.get("roi")),
                "judge_scores": judge_scores,
                "patch_version": row.get("patch_version"),
                "completed_at": row.get("completed_at"),
            }
        )
    return history


def get_patch_impact(conn, patch_version: str) -> dict:
    patch_sql = f"SELECT applied_at FROM patches WHERE version={_param(conn)}"
    patch_row = _fetch_one(conn, patch_sql, (patch_version,))
    applied_at = patch_row.get("applied_at") if patch_row else None

    if applied_at:
        impact_sql = (
            "SELECT "
            f"AVG(CASE WHEN completed_at < {_param(conn)} THEN roi END) AS before_avg_roi, "
            f"AVG(CASE WHEN completed_at >= {_param(conn)} THEN roi END) AS after_avg_roi, "
            "COUNT(DISTINCT agent_id) AS agent_count, "
            "COUNT(*) AS round_count "
            "FROM tournament_rounds "
            f"WHERE status={_param(conn)} AND roi IS NOT NULL"
        )
        params: tuple[Any, ...] = (applied_at, applied_at, "completed")
    else:
        impact_sql = (
            "SELECT "
            f"AVG(CASE WHEN patch_version <> {_param(conn)} THEN roi END) AS before_avg_roi, "
            f"AVG(CASE WHEN patch_version = {_param(conn)} THEN roi END) AS after_avg_roi, "
            "COUNT(DISTINCT agent_id) AS agent_count, "
            "COUNT(*) AS round_count "
            "FROM tournament_rounds "
            f"WHERE status={_param(conn)} AND roi IS NOT NULL"
        )
        params = (patch_version, patch_version, "completed")

    row = _fetch_one(conn, impact_sql, params) or {}
    return {
        "before_avg_roi": _safe_float(row.get("before_avg_roi")),
        "after_avg_roi": _safe_float(row.get("after_avg_roi")),
        "agent_count": _safe_int(row.get("agent_count"), 0),
        "round_count": _safe_int(row.get("round_count"), 0),
    }
