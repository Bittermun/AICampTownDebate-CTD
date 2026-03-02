"""
Match Registry — Cross-Session Persistent Storage

Stores tournament run data across sessions for longitudinal analysis.

Backend selection (via env var MATCH_REGISTRY_URL):
  - Unset or "sqlite"  → local SQLite at logs/match_registry.db  (default, zero config)
  - "postgresql://..."  → Postgres / Supabase connection string
  - "supabase"         → reads SUPABASE_URL + SUPABASE_KEY env vars

Schema (Supabase-compatible SQL; SQLite uses same column names):
  tournament_runs   — one row per tournament
  round_results     — one row per debate round within a tournament

Usage:
    from src.integrations.match_registry import MatchRegistry
    registry = MatchRegistry()
    run_id = registry.log_tournament(result, health_report, config_label="default")
    # Later:
    df = registry.query_runs(limit=50)
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

# ── Optional Postgres/Supabase support (requires psycopg2 or supabase-py) ────
try:
    import psycopg2
    import psycopg2.extras
    _HAS_PSYCOPG2 = True
except ImportError:
    _HAS_PSYCOPG2 = False

_SQLITE_DDL = """
CREATE TABLE IF NOT EXISTS tournament_runs (
    id              TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    config_label    TEXT,
    model_a         TEXT,
    model_b         TEXT,
    topics_count    INTEGER,
    rounds_count    INTEGER,
    winner          TEXT,
    final_balance_a REAL,
    final_balance_b REAL,
    health_score    REAL,
    judge_margin    REAL,
    adaptation_gain REAL,
    economy_reason  REAL,
    pass_rate       REAL,
    kelly_regret    REAL,
    meta            TEXT
);

CREATE TABLE IF NOT EXISTS round_results (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES tournament_runs(id),
    round_num       INTEGER,
    topic           TEXT,
    confidence_a    REAL,
    confidence_b    REAL,
    margin          REAL,
    bets_placed     INTEGER,
    iterations      INTEGER
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


class MatchRegistry:
    """
    Persistent cross-session storage for tournament runs.

    Automatically selects SQLite (local) or Postgres backend based on
    MATCH_REGISTRY_URL environment variable.
    """

    def __init__(self, db_path: str = "logs/match_registry.db"):
        self._backend = os.environ.get("MATCH_REGISTRY_URL", "sqlite").lower()
        self._db_path = db_path
        self._pg_conn = None

        if self._backend == "sqlite" or not self._backend:
            self._init_sqlite()
        elif self._backend.startswith("postgresql") or self._backend.startswith("postgres"):
            self._init_postgres(self._backend)
        elif self._backend == "supabase":
            url = os.environ.get("SUPABASE_URL", "")
            # Supabase Postgres connection string format
            # Convert https://xxx.supabase.co → postgres://... (user provides full URL)
            pg_url = os.environ.get("SUPABASE_DB_URL", url)
            self._init_postgres(pg_url)
        else:
            print(f"[MatchRegistry] Unknown backend '{self._backend}', falling back to SQLite")
            self._backend = "sqlite"
            self._init_sqlite()

    def _init_sqlite(self):
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.executescript(_SQLITE_DDL)
        conn.commit()
        conn.close()
        print(f"[MatchRegistry] SQLite backend: {Path(self._db_path).resolve()}")

    def _init_postgres(self, url: str):
        if not _HAS_PSYCOPG2:
            print("[MatchRegistry] psycopg2 not installed; falling back to SQLite")
            self._backend = "sqlite"
            self._init_sqlite()
            return
        try:
            self._pg_conn = psycopg2.connect(url)
            with self._pg_conn.cursor() as cur:
                # Create tables if not exists (same schema, Postgres-compatible)
                pg_ddl = _SQLITE_DDL.replace("TEXT PRIMARY KEY", "TEXT PRIMARY KEY DEFAULT gen_random_uuid()")
                cur.execute(pg_ddl)
            self._pg_conn.commit()
            print("[MatchRegistry] Postgres/Supabase backend connected")
        except Exception as e:
            print(f"[MatchRegistry] Postgres connection failed ({e}); falling back to SQLite")
            self._backend = "sqlite"
            self._init_sqlite()

    # ── Core logging methods ──────────────────────────────────────────────────

    def log_tournament(
        self,
        tournament_result: Any,
        health_report: Any = None,
        config_label: str = "default",
        kelly_regret: float = 0.0,
        meta: dict | None = None,
    ) -> str:
        """
        Log a completed tournament to the registry.

        Args:
            tournament_result: TournamentResult object from arena/tournament.py
            health_report:     SelectionHealthReport from analysis/selection_health.py
            config_label:      Human label for this config/experiment variant
            kelly_regret:      Mean |actual - optimal| bet size
            meta:              Any extra key-value pairs to store as JSON

        Returns:
            run_id (str): UUID of the inserted row
        """
        run_id = _new_id()

        debater_a_name = getattr(tournament_result, "debater_a_name",
            list(tournament_result.final_balances.keys())[0] if tournament_result.final_balances else "A")
        debater_b_name = getattr(tournament_result, "debater_b_name",
            list(tournament_result.final_balances.keys())[1] if len(tournament_result.final_balances) > 1 else "B")

        bal_a = tournament_result.final_balances.get(debater_a_name, 0.0)
        bal_b = tournament_result.final_balances.get(debater_b_name, 0.0)

        rounds = tournament_result.rounds or []

        # Extract model names from round results if available
        model_a = getattr(tournament_result.config, "model_a", config_label)
        model_b = getattr(tournament_result.config, "model_b", config_label)

        run_row = {
            "id": run_id,
            "created_at": _now_iso(),
            "config_label": config_label,
            "model_a": model_a,
            "model_b": model_b,
            "topics_count": len(rounds),
            "rounds_count": len(rounds),
            "winner": tournament_result.winner or "TIE",
            "final_balance_a": round(bal_a, 2),
            "final_balance_b": round(bal_b, 2),
            "health_score": round(health_report.health_score, 4) if health_report else None,
            "judge_margin": round(health_report.judge_margin_mean, 4) if health_report else None,
            "adaptation_gain": round(health_report.adaptation_gain_after_loss, 4) if health_report else None,
            "economy_reason": round(health_report.economy_reasoning_rate, 4) if health_report else None,
            "pass_rate": round(health_report.pass_rate, 4) if health_report else None,
            "kelly_regret": round(kelly_regret, 4),
            "meta": json.dumps(meta or {}),
        }

        round_rows = []
        for r in rounds:
            final_j = getattr(r, "final_judgment", None) or getattr(r, "judgment", None)
            conf_a = getattr(final_j, "confidence_a", 0.5) if final_j else 0.5
            conf_b = getattr(final_j, "confidence_b", 0.5) if final_j else 0.5
            round_rows.append({
                "id": _new_id(),
                "run_id": run_id,
                "round_num": getattr(r, "round_id", 0),
                "topic": getattr(r, "topic", ""),
                "confidence_a": round(conf_a, 4),
                "confidence_b": round(conf_b, 4),
                "margin": round(abs(conf_a - conf_b), 4),
                "bets_placed": len(getattr(r, "all_bets", getattr(r, "bets_placed", []))),
                "iterations": getattr(r, "iterations_completed", 1),
            })

        if self._backend == "sqlite":
            self._sqlite_insert(run_row, round_rows)
        else:
            self._postgres_insert(run_row, round_rows)

        print(f"[MatchRegistry] Run {run_id[:8]}... logged ({len(round_rows)} rounds)")
        return run_id

    def _sqlite_insert(self, run_row: dict, round_rows: list[dict]):
        conn = sqlite3.connect(self._db_path)
        cols = list(run_row.keys())
        placeholders = ",".join("?" for _ in cols)
        conn.execute(
            f"INSERT OR REPLACE INTO tournament_runs ({','.join(cols)}) VALUES ({placeholders})",
            [run_row[c] for c in cols],
        )
        for rr in round_rows:
            rcols = list(rr.keys())
            rph = ",".join("?" for _ in rcols)
            conn.execute(
                f"INSERT OR REPLACE INTO round_results ({','.join(rcols)}) VALUES ({rph})",
                [rr[c] for c in rcols],
            )
        conn.commit()
        conn.close()

    def _postgres_insert(self, run_row: dict, round_rows: list[dict]):
        with self._pg_conn.cursor() as cur:
            cols = list(run_row.keys())
            placeholders = ",".join(f"%({c})s" for c in cols)
            cur.execute(
                f"INSERT INTO tournament_runs ({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING",
                run_row,
            )
            for rr in round_rows:
                rcols = list(rr.keys())
                rph = ",".join(f"%({c})s" for c in rcols)
                cur.execute(
                    f"INSERT INTO round_results ({','.join(rcols)}) VALUES ({rph}) ON CONFLICT (id) DO NOTHING",
                    rr,
                )
        self._pg_conn.commit()

    # ── Query helpers ─────────────────────────────────────────────────────────

    def query_runs(self, limit: int = 50) -> list[dict]:
        """Return last N tournament runs, newest first."""
        if self._backend == "sqlite":
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM tournament_runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        else:
            with self._pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM tournament_runs ORDER BY created_at DESC LIMIT %s", (limit,)
                )
                return [dict(r) for r in cur.fetchall()]

    def print_leaderboard(self, limit: int = 20):
        """Print a formatted leaderboard of recent tournament runs."""
        runs = self.query_runs(limit=limit)
        if not runs:
            print("[MatchRegistry] No runs recorded yet.")
            return
        print(f"\n{'═'*72}")
        print(f"  MATCH REGISTRY — Last {min(limit, len(runs))} Runs")
        print(f"{'═'*72}")
        print(f"  {'Date':>10}  {'Winner':>16}  {'Bal A':>7}  {'Bal B':>7}  {'Health':>6}  {'Margin':>6}  Config")
        print(f"  {'─'*65}")
        for r in runs:
            date = r.get("created_at", "")[:10]
            winner = (r.get("winner") or "TIE")[:16]
            bal_a = r.get("final_balance_a") or 0
            bal_b = r.get("final_balance_b") or 0
            health = r.get("health_score") or 0
            margin = r.get("judge_margin") or 0
            label = (r.get("config_label") or "")[:12]
            print(f"  {date:>10}  {winner:>16}  {bal_a:>7.1f}  {bal_b:>7.1f}  {health:>6.3f}  {margin:>6.3f}  {label}")
        print(f"{'═'*72}")

    def summary_stats(self) -> dict:
        """Return aggregate stats across all stored runs."""
        if self._backend == "sqlite":
            conn = sqlite3.connect(self._db_path)
            row = conn.execute("""
                SELECT
                    COUNT(*) as total_runs,
                    AVG(health_score) as avg_health,
                    AVG(judge_margin) as avg_margin,
                    AVG(kelly_regret) as avg_kelly_regret,
                    AVG(adaptation_gain) as avg_adaptation,
                    SUM(CASE WHEN winner = final_balance_a THEN 1 ELSE 0 END) as a_wins
                FROM tournament_runs
            """).fetchone()
            conn.close()
            if row:
                return {
                    "total_runs": row[0],
                    "avg_health": round(row[1] or 0, 4),
                    "avg_margin": round(row[2] or 0, 4),
                    "avg_kelly_regret": round(row[3] or 0, 4),
                    "avg_adaptation": round(row[4] or 0, 4),
                }
        return {}
