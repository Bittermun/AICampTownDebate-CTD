"""
verify_all.py
Run ALL verify commands from CODEX_QUEUE.md in sequence.
Usage: python scripts/verify_all.py [--tasks 001 002 003 ...]
       python scripts/verify_all.py          # run all tasks
       python scripts/verify_all.py --batch B  # run all batch-B tasks

Each task's verify command is embedded here as a Python function.
Output: PASS/FAIL per task, summary at end.
"""

import sys
import sqlite3
import argparse
import traceback
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ── helpers ────────────────────────────────────────────────────────────────

def result(task_id, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] TASK-{task_id}"
    if detail:
        line += f"  {detail}"
    print(line)
    return ok


# ── TASK-001: schema creates all expected tables ───────────────────────────

def verify_001():
    try:
        sql_path = ROOT / "src/db/schema_sqlite.sql"
        if not sql_path.exists():
            return result("001", False, "src/db/schema_sqlite.sql not found")
        sql = sql_path.read_text(encoding="utf-8")
        conn = sqlite3.connect(":memory:")
        conn.executescript(sql)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        expected = [
            "provider_configs", "patches", "agents", "agent_state_snapshots",
            "tournaments", "tournament_participants", "tournament_rounds"
        ]
        missing = [t for t in expected if t not in tables]
        if missing:
            return result("001", False, f"missing tables: {missing}")
        return result("001", True, f"{len(tables)} tables OK")
    except Exception as e:
        return result("001", False, str(e))


# ── TASK-002: DB connection returns valid connection with expected tables ──

def verify_002():
    try:
        from src.db.connection import get_db
        db = get_db()
        tables = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        ok = "agents" in tables and "tournament_rounds" in tables
        return result("002", ok, f"tables={tables[:4]}...")
    except Exception as e:
        return result("002", False, str(e))


# ── TASK-003: ops CRUD round-trip ─────────────────────────────────────────

def verify_003():
    try:
        from src.db.connection import get_db
        from src.db import ops
        conn = get_db()
        ops.upsert_agent(conn, "verify_003_agent", "VerifyAgent", None)
        a = ops.get_agent(conn, "verify_003_agent")
        if not a or a["name"] != "VerifyAgent":
            return result("003", False, f"agent mismatch: {a}")
        ops.create_tournament(conn, "verify_003_t1", "{}", None, 42)
        ops.update_tournament_status(conn, "verify_003_t1", "running")
        t = ops.get_tournament(conn, "verify_003_t1")
        if not t or t["status"] != "running":
            return result("003", False, f"tournament mismatch: {t}")
        conn.commit()
        return result("003", True, "agent + tournament CRUD OK")
    except Exception as e:
        return result("003", False, str(e))


# ── TASK-004A: ProviderBackend importable ─────────────────────────────────

def verify_004A():
    try:
        from src.models.provider_backend import ProviderBackend, ProviderConfig
        return result("004A", True, "ProviderBackend + ProviderConfig importable")
    except Exception as e:
        return result("004A", False, str(e))


# ── TASK-004B: legacy backends deleted, tests pass ────────────────────────

def verify_004B():
    import subprocess
    legacy_files = [
        "src/models/ollama_backend.py",
        "src/models/vllm_backend.py",
        "src/models/openai_compat_backend.py",
    ]
    still_present = [f for f in legacy_files if (ROOT / f).exists()]
    if still_present:
        return result("004B", False, f"still present: {still_present}")
    # Confirm GenerationResult importable from provider_backend and __init__
    try:
        from src.models.provider_backend import GenerationResult
        from src.models import GenerationResult as GR2  # noqa: F401
    except Exception as e:
        return result("004B", False, f"GenerationResult import failed: {e}")
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-x", "-q"],
        capture_output=True, text=True, cwd=ROOT
    )
    passed = r.returncode == 0
    tail = (r.stdout + r.stderr).strip().split("\n")[-1]
    return result("004B", passed, tail)


# ── TASK-005: patch registration ──────────────────────────────────────────

def verify_005():
    import subprocess
    r = subprocess.run(
        [sys.executable, "scripts/register_patch.py",
         "--version", "v_verify_005",
         "--description", "verify_all test patch",
         "--affected", "test",
         "--delta", "{}"],
        capture_output=True, text=True, cwd=ROOT
    )
    if r.returncode != 0:
        return result("005", False, r.stderr.strip()[:120])
    try:
        from src.db.connection import get_db
        p = get_db().execute(
            "SELECT * FROM patches WHERE version='v_verify_005'"
        ).fetchone()
        return result("005", p is not None, "patch row present" if p else "patch row missing")
    except Exception as e:
        return result("005", False, str(e))


# ── TASK-006: agent registry ──────────────────────────────────────────────

def verify_006():
    try:
        from src.db.connection import get_db
        from src.db.agent_registry import register_agent, apply_patch_notification
        conn = get_db()
        aid = register_agent(conn, "qwen/qwen3-32b", "https://api.groq.com/openai/v1")
        if not aid or len(aid) < 3:
            return result("006", False, f"bad agent id: {aid!r}")
        conn.commit()
        return result("006", True, f"agent id={aid}")
    except Exception as e:
        return result("006", False, str(e))


# ── TASK-007: health check returns False on dead endpoint ─────────────────

def verify_007():
    try:
        from src.db.health_check import check_provider
        from src.models.provider_backend import ProviderConfig
        res = check_provider(ProviderConfig(base_url="http://localhost:1", model="x"))
        return result("007", res is False, "dead endpoint returns False cleanly")
    except Exception as e:
        return result("007", False, str(e))


# ── TASK-008: RoundWriter begin/complete cycle ────────────────────────────

def verify_008():
    import uuid
    try:
        from src.db.connection import get_db
        from src.db.ops import upsert_agent, create_tournament
        from src.db.round_writer import RoundWriter
        conn = get_db()
        upsert_agent(conn, "verify_008_a", "TestAgent", None)
        create_tournament(conn, "verify_008_t", "{}", None, 1)
        conn.commit()
        rw = RoundWriter(conn, "verify_008_t", "v1.0")
        key = rw.begin_round(1, "verify_008_a")
        rw.complete_round(key, {"text": "hello"}, 100, {"accuracy": 0.7}, 0.05)
        conn.commit()
        row = conn.execute(
            "SELECT status FROM tournament_rounds WHERE idempotency_key=?", (key,)
        ).fetchone()
        ok = row is not None and row["status"] == "completed"
        return result("008", ok, f"status={row['status'] if row else None}")
    except Exception as e:
        return result("008", False, str(e))


# ── TASK-009: resume loader returns correct next round ────────────────────

def verify_009():
    import uuid
    try:
        from src.db.connection import get_db
        from src.db.ops import create_tournament, insert_round, update_round
        from src.db.resume import get_resume_point, mark_stale_rounds_dead
        conn = get_db()
        create_tournament(conn, "verify_009_rt", "{}", None, 99)
        insert_round(conn, str(uuid.uuid4()), "verify_009_rt", 1, None, "v1.0")
        key2 = str(uuid.uuid4())
        insert_round(conn, key2, "verify_009_rt", 2, None, "v1.0")
        update_round(conn, key2, "completed")
        conn.commit()
        pt = get_resume_point(conn, "verify_009_rt")
        return result("009", pt == 3, f"resume_point={pt} (expected 3)")
    except Exception as e:
        return result("009", False, str(e))


# ── TASK-010: leaderboard returns list, patch_impact returns dict ─────────

def verify_010():
    try:
        from src.db.connection import get_db
        from src.db.leaderboard import get_leaderboard, get_patch_impact
        conn = get_db()
        lb = get_leaderboard(conn)
        pi = get_patch_impact(conn, "nonexistent_patch")
        ok = isinstance(lb, list) and isinstance(pi, dict)
        return result("010", ok, f"leaderboard={len(lb)} rows, patch_impact keys={list(pi.keys())}")
    except Exception as e:
        return result("010", False, str(e))


# ── TASK-011: config bridge registers agents from YAML ────────────────────

def verify_011():
    import os
    os.environ.setdefault("OPENAI_COMPAT_BASE_URL", "https://api.groq.com/openai/v1")
    try:
        from src.db.connection import get_db
        from src.db.config_bridge import register_from_yaml
        conn = get_db()
        ids = register_from_yaml(conn, str(ROOT / "configs/clean_economy_groq.yaml"))
        conn.commit()
        ok = len(ids) >= 2
        return result("011", ok, f"registered {len(ids)} agents: {ids}")
    except Exception as e:
        return result("011", False, str(e))


# ── TASK-012: migration imports clean_100 runs into DB ────────────────────

def verify_012():
    import subprocess
    batch_dir = ROOT / "logs/clean_overnight_01/clean_100"
    if not batch_dir.exists():
        return result("012", False, f"batch dir not found: {batch_dir}")
    r = subprocess.run(
        [sys.executable, "scripts/migrate_json_logs.py",
         "--batch-dir", str(batch_dir)],
        capture_output=True, text=True, cwd=ROOT
    )
    if r.returncode != 0:
        return result("012", False, r.stderr.strip()[:200])
    try:
        from src.db.connection import get_db
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) FROM tournaments").fetchone()[0]
        ok = count >= 90
        return result("012", ok, f"{count} tournaments in DB (expected ~99)")
    except Exception as e:
        return result("012", False, str(e))


# ── TASK-013: round_writer param present in DynamicDebateRound ────────────

def verify_013():
    import inspect
    try:
        from src.arena.dynamic_round import DynamicDebateRound
        sig = inspect.signature(DynamicDebateRound.__init__)
        ok = "round_writer" in sig.parameters
        return result("013", ok, "round_writer parameter present" if ok else "round_writer param MISSING")
    except Exception as e:
        return result("013", False, str(e))


# ── TASK-014: run_league.py exists and is parseable Python ────────────────

def verify_014():
    import ast
    rl = ROOT / "run_league.py"
    if not rl.exists():
        return result("014", False, "run_league.py missing from repo root")
    try:
        tree = ast.parse(rl.read_text(encoding="utf-8"))
        fns = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        return result("014", True, f"functions: {fns}")
    except SyntaxError as e:
        return result("014", False, f"SyntaxError: {e}")


# ── dispatch ───────────────────────────────────────────────────────────────

TASKS = {
    "001":  (verify_001,  "A"),
    "002":  (verify_002,  "B"),
    "003":  (verify_003,  "B"),
    "004A": (verify_004A, "B"),
    "004B": (verify_004B, "B"),
    "005":  (verify_005,  "B"),
    "006":  (verify_006,  "B"),
    "007":  (verify_007,  "C"),
    "008":  (verify_008,  "C"),
    "009":  (verify_009,  "C"),
    "010":  (verify_010,  "C"),
    "011":  (verify_011,  "D"),
    "012":  (verify_012,  "D"),
    "013":  (verify_013,  "D"),
    "014":  (verify_014,  "D"),
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", nargs="*", help="specific task IDs (e.g. 001 002 004A)")
    parser.add_argument("--batch", help="run all tasks in a batch (A/B/C/D)")
    args = parser.parse_args()

    if args.tasks:
        to_run = {t: TASKS[t] for t in args.tasks if t in TASKS}
        unknown = [t for t in args.tasks if t not in TASKS]
        if unknown:
            print(f"[warn] unknown task IDs: {unknown}")
    elif args.batch:
        b = args.batch.upper()
        to_run = {k: v for k, v in TASKS.items() if v[1] == b}
        if not to_run:
            print(f"[error] no tasks in batch {b}")
            sys.exit(1)
    else:
        to_run = TASKS

    print(f"\nverify_all.py — running {len(to_run)} task(s)\n")
    results = {}
    for task_id, (fn, batch) in to_run.items():
        print(f"TASK-{task_id} [batch {batch}]")
        try:
            results[task_id] = fn()
        except Exception as e:
            results[task_id] = result(task_id, False, f"exception: {e}")
            traceback.print_exc()
        print()

    passed = sum(1 for v in results.values() if v)
    failed = len(results) - passed
    print("─" * 50)
    print(f"SUMMARY: {passed} passed, {failed} failed out of {len(results)}")
    if failed:
        print("\nFailed tasks:")
        for task_id, ok in results.items():
            if not ok:
                print(f"  TASK-{task_id}")
        sys.exit(1)
    else:
        print("All tasks passed.")

if __name__ == "__main__":
    main()
