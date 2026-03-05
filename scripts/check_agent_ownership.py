#!/usr/bin/env python3
"""Agent ownership scope checker.

Supports two operating modes:
- warn: report out-of-scope files, exit 0
- gate: report out-of-scope files, exit non-zero

Use this with either:
- explicit file list (`--files` / `--files-from`)
- current git working tree (`--use-git-status`)
"""
from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List


AGENT_SCOPES: dict[str, list[str]] = {
    "A": [
        "docs/EVALUATION_CONTRACT.md",
        "docs/BENCHMARK_PROTOCOL.md",
        "docs/NEXT_AI_BOOTSTRAP.md",
        "configs/benchmark_phase1.yaml",
        "scripts/audit_score_ceiling.py",
        "scripts/reconcile_settlement.py",
        "src/benchmark/scoring.py",
        "src/benchmark/config_models.py",
        "src/benchmark/registry.py",
    ],
    "B": [
        "scripts/run_phase1_batch.py",
        "scripts/run_tournament_batch.py",
        "tests/test_phase1_batch_endpoint_assignment.py",
        "tests/test_run_tournament_batch_resume.py",
        "src/benchmark/batch_utils.py",
    ],
    "C": [
        "src/models/debater.py",
        "src/config_loader.py",
        "demo_tournament.py",
        "demo_dynamic.py",
        "configs/multi_agent_experimental.yaml",
        "tests/test_debater_multi_agent.py",
        "tests/reproduce_multi_agent_ablation.py",
        "tests/test_benchmark_config_parse.py",
        "README.md",
        "docs/PROCEDURES.md",
    ],
}

SHARED_FILES = {
    "src/benchmark/runner.py",
    "DEVLOG.md",
    "AGENT_FORUM.md",
    "HANDOFF.md",
    "docs/MULTI_AGENT_EXECUTION_PROTOCOL_20260305.md",
    "scripts/check_agent_ownership.py",
}


def _norm_path(p: str) -> str:
    return p.strip().replace("\\", "/")


def _read_files_from_file(path: Path) -> list[str]:
    rows = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        rows.append(_norm_path(s))
    return rows


def _parse_git_status_files() -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git status failed")

    files: list[str] = []
    for line in proc.stdout.splitlines():
        if not line:
            continue
        payload = line[3:] if len(line) >= 4 else line
        if "->" in payload:
            payload = payload.split("->", 1)[1]
        files.append(_norm_path(payload))
    return files


def _matches_scope(path: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)


def main() -> int:
    p = argparse.ArgumentParser(description="Check changed files against agent ownership scope")
    p.add_argument("--agent", required=True, choices=["A", "B", "C"], help="Agent lane ID")
    p.add_argument(
        "--mode",
        default="warn",
        choices=["warn", "gate"],
        help="warn: always exit 0, gate: non-zero on out-of-scope files",
    )
    p.add_argument("--files", nargs="*", default=[], help="Explicit file paths to check")
    p.add_argument("--files-from", default="", help="File containing one path per line")
    p.add_argument("--use-git-status", action="store_true", help="Read file list from git working tree")
    p.add_argument(
        "--allow-shared",
        action="store_true",
        default=True,
        help="Allow edits to shared coordination files",
    )
    p.add_argument(
        "--ignore",
        nargs="*",
        default=[],
        help="Optional fnmatch patterns to ignore from checks",
    )
    args = p.parse_args()

    candidates: list[str] = []
    if args.files:
        candidates.extend(_norm_path(x) for x in args.files)
    if args.files_from:
        candidates.extend(_read_files_from_file(Path(args.files_from)))
    if args.use_git_status:
        candidates.extend(_parse_git_status_files())

    if not candidates:
        print("[scope] no files provided (use --files, --files-from, or --use-git-status)")
        return 2

    # Deduplicate while preserving order.
    seen = set()
    files = []
    for f in candidates:
        if f in seen:
            continue
        seen.add(f)
        files.append(f)

    ignore_pats = list(args.ignore or [])
    files = [f for f in files if not _matches_scope(f, ignore_pats)]

    scope = AGENT_SCOPES[args.agent]
    shared_touched: List[str] = []
    in_scope: List[str] = []
    out_scope: List[str] = []

    for f in files:
        if args.allow_shared and f in SHARED_FILES:
            shared_touched.append(f)
            continue
        if _matches_scope(f, scope):
            in_scope.append(f)
        else:
            out_scope.append(f)

    print(f"[scope] agent={args.agent} mode={args.mode}")
    print(f"[scope] checked={len(files)} in_scope={len(in_scope)} shared={len(shared_touched)} out_of_scope={len(out_scope)}")

    if in_scope:
        print("[scope] in-scope:")
        for f in in_scope:
            print(f"  - {f}")
    if shared_touched:
        print("[scope] shared files (lock required):")
        for f in shared_touched:
            print(f"  - {f}")
    if out_scope:
        print("[scope] OUT-OF-SCOPE:")
        for f in out_scope:
            print(f"  - {f}")

    if args.mode == "gate" and out_scope:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
