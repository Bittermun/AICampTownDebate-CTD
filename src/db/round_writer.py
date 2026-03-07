# TASK-008 output - see CODEX_QUEUE.md
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from .ops import insert_round, update_round


def _is_sqlite(conn) -> bool:
    return conn.__class__.__module__.startswith("sqlite3")


def _param(conn) -> str:
    return "?" if _is_sqlite(conn) else "%s"


def _fetch_retry_count(conn, idempotency_key: str):
    sql = f"SELECT retry_count FROM tournament_rounds WHERE idempotency_key={_param(conn)}"
    if _is_sqlite(conn):
        return conn.execute(sql, (idempotency_key,)).fetchone()
    cur = conn.cursor()
    try:
        cur.execute(sql, (idempotency_key,))
        return cur.fetchone()
    finally:
        cur.close()


class RoundWriter:
    def __init__(self, conn, tournament_id: str, patch_version: str):
        self.conn = conn
        self.tournament_id = tournament_id
        self.patch_version = patch_version

    def begin_round(self, round_number: int, agent_id: str) -> str:
        idempotency_key = str(uuid.uuid4())
        insert_round(
            self.conn,
            idempotency_key=idempotency_key,
            tournament_id=self.tournament_id,
            round_number=round_number,
            agent_id=agent_id,
            patch_version=self.patch_version,
        )
        return idempotency_key

    def complete_round(
        self,
        idempotency_key: str,
        transcript: dict,
        tokens_used: int,
        judge_scores: dict,
        roi: float,
    ) -> None:
        completed_at = datetime.now(timezone.utc).isoformat()
        update_round(
            self.conn,
            idempotency_key=idempotency_key,
            status="completed",
            transcript_json=json.dumps(transcript),
            tokens_used=tokens_used,
            judge_scores=json.dumps(judge_scores),
            roi=roi,
            completed_at=completed_at,
        )

    def fail_round(self, idempotency_key: str, reason: str) -> None:
        try:
            row = _fetch_retry_count(self.conn, idempotency_key)
            if row is None:
                return

            retry_count = int(row["retry_count"] if hasattr(row, "keys") else row[0]) + 1
            status = "dead" if retry_count >= 3 else "failed"
            update_round(
                self.conn,
                idempotency_key=idempotency_key,
                status=status,
                retry_count=retry_count,
                judge_scores=json.dumps({"error": reason}),
            )
        except Exception:
            return
