#!/usr/bin/env python3
"""Run many strict tournament jobs and archive per-run dataset artifacts."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.analysis import assign_trace_quality_tier, export_trace_jsonl, normalize_transcript_to_traces
from src.benchmark.batch_utils import (
    BATCH_CHECKPOINT_FILENAME as CHECKPOINT_FILENAME,
    BATCH_CHECKPOINT_SCHEMA_VERSION as CHECKPOINT_SCHEMA_VERSION,
    append_jsonl,
    assert_resume_compatible as _assert_resume_compatible,
    atomic_write_json as _atomic_write_json,
    build_batch_checkpoint_payload,
    load_batch_checkpoint as _load_checkpoint,
    load_checkpoint_jsonl,
    persist_jsonl,
)
from src.config_loader import load_config

TOURNAMENT_SUMMARY_SCHEMA_NAME = "benchmark.tournament.batch_summary"


def _is_model_prefix(model_id: Optional[str], prefix: str) -> bool:
    return bool(model_id) and str(model_id).startswith(f"{prefix}:")


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _mean(values: List[float]) -> float:
    return (sum(values) / len(values)) if values else 0.0


def _atomic_write_jsonl_records(path: Path, records: List[Dict[str, Any]]) -> None:
    persist_jsonl(
        str(path),
        records,
        schema_name=TOURNAMENT_SUMMARY_SCHEMA_NAME,
    )


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    append_jsonl(
        str(path),
        payload,
        schema_name=TOURNAMENT_SUMMARY_SCHEMA_NAME,
    )


def _config_fingerprint(args: argparse.Namespace, base_urls: List[str]) -> str:
    payload = {
        "config": args.config,
        "runs": int(args.runs),
        "start_seed": int(args.start_seed),
        "seed_step": int(args.seed_step),
        "allow_stub": bool(args.allow_stub),
        "gate_variance_enabled": not bool(args.no_gate_judge_variance),
        "gate_calibration_enabled": not bool(args.no_gate_judge_calibration),
        "variance_runs": int(args.variance_runs),
        "max_judge_stdev": float(args.max_judge_stdev),
        "min_judge_mean_a": float(args.min_judge_mean_a),
        "min_calibration_pass_rate": float(args.min_calibration_pass_rate),
        "openai_base_urls": list(base_urls),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _checkpoint_payload(batch_id: str, fingerprint: str) -> Dict[str, Any]:
    return build_batch_checkpoint_payload(batch_id=batch_id, config_fingerprint=fingerprint)


def _load_summary_records(path: Path) -> List[Dict[str, Any]]:
    records, stats = load_checkpoint_jsonl(
        str(path),
        schema_name=TOURNAMENT_SUMMARY_SCHEMA_NAME,
    )
    if stats["rows_malformed"] or stats["rows_invalid"]:
        print(
            f"[batch][warn] summary decode issues: malformed={stats['rows_malformed']} "
            f"invalid={stats['rows_invalid']}"
        )
    if stats["rows_legacy"]:
        print(f"[batch] migrated legacy summary rows={stats['rows_legacy']} -> schema=v1")
    return records


def _index_records_by_run_no(
    records: List[Dict[str, Any]],
    runs_requested: int,
) -> Dict[int, Dict[str, Any]]:
    indexed: Dict[int, Dict[str, Any]] = {}
    for record in records:
        run_no = record.get("run_no")
        if isinstance(run_no, int) and 1 <= run_no <= runs_requested:
            indexed[run_no] = record
    return indexed


def _build_jobs(
    *,
    runs: int,
    start_seed: int,
    seed_step: int,
    base_urls: List[str],
    skip_run_nos: Optional[set[int]] = None,
) -> List[tuple[int, int, Optional[str]]]:
    jobs: List[tuple[int, int, Optional[str]]] = []
    for idx in range(runs):
        run_no = idx + 1
        if skip_run_nos and run_no in skip_run_nos:
            continue
        seed = start_seed + idx * seed_step
        endpoint = base_urls[idx % len(base_urls)] if base_urls else None
        jobs.append((run_no, seed, endpoint))
    return jobs


def _build_exception_record(run_no: int, seed: int, endpoint: Optional[str], error: str) -> Dict[str, Any]:
    return {
        "run_no": run_no,
        "seed": seed,
        "run_dir": "",
        "started_at": "",
        "ended_at": "",
        "exit_code": 9,
        "success": False,
        "winner": None,
        "rounds_completed": 0,
        "eliminated": None,
        "health_score": None,
        "pass_rate": None,
        "aggression_rate": None,
        "adaptation_gain_after_loss": None,
        "trace_count": 0,
        "trace_quality_tier": "tier_c",
        "endpoint": endpoint,
        "error": error,
        "artifact_paths": {},
    }


def _infer_gate_passes_from_exit_code(
    *,
    exit_code: int,
    gate_variance_enabled: bool,
    gate_calibration_enabled: bool,
) -> Dict[str, Optional[bool]]:
    """
    Infer explicit gate pass/fail states from demo_tournament exit codes.

    demo_tournament exit codes:
    - 0: run success (all enabled gates passed)
    - 3: variance gate failed
    - 4: calibration gate failed
    - others: runtime/preflight failure (gate outcome unknown)
    """
    variance_pass: Optional[bool] = None
    calibration_pass: Optional[bool] = None

    if gate_variance_enabled:
        if exit_code == 3:
            variance_pass = False
        elif exit_code in (0, 4):
            variance_pass = True

    if gate_calibration_enabled:
        if exit_code == 4:
            calibration_pass = False
        elif exit_code == 0:
            calibration_pass = True

    return {
        "judge_variance_pass": variance_pass,
        "judge_calibration_pass": calibration_pass,
    }


def _run_tournament_job(
    run_no: int,
    seed: int,
    batch_root: Path,
    batch_id: str,
    args: argparse.Namespace,
    gate_variance: bool,
    gate_calibration: bool,
    judge_model: str,
    summary_jsonl: Path,
    write_lock: threading.Lock,
    openai_base_url: Optional[str],
) -> Dict[str, Any]:
    run_dir = batch_root / f"run_{run_no:03d}_seed_{seed}"
    run_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "demo_tournament.py",
        "--config",
        args.config,
        "--seed",
        str(seed),
        "--output-dir",
        str(run_dir),
        "--output-prefix",
        "tournament_results",
    ]
    if args.allow_stub:
        cmd.append("--allow-stub")
    if gate_variance:
        cmd.extend(
            [
                "--gate-judge-variance",
                "--variance-runs",
                str(args.variance_runs),
                "--max-judge-stdev",
                str(args.max_judge_stdev),
                "--min-judge-mean-a",
                str(args.min_judge_mean_a),
            ]
        )
    if gate_calibration:
        cmd.extend(
            [
                "--gate-judge-calibration",
                "--min-calibration-pass-rate",
                str(args.min_calibration_pass_rate),
            ]
        )

    env = os.environ.copy()
    if openai_base_url:
        endpoint_env = getattr(args, "_endpoint_env", {"openai": True, "vllm": True, "ollama": True})
        if endpoint_env.get("openai"):
            env["OPENAI_COMPAT_BASE_URL"] = openai_base_url
        if endpoint_env.get("vllm"):
            env["VLLM_BASE_URL"] = openai_base_url
        if endpoint_env.get("ollama"):
            env["OLLAMA_HOST"] = openai_base_url

    started_at = datetime.now(timezone.utc).isoformat()
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    ended_at = datetime.now(timezone.utc).isoformat()

    (run_dir / "run.log").write_text(
        "\n".join(
            [
                f"CMD: {' '.join(cmd)}",
                f"ENDPOINT: {openai_base_url or 'default'}",
                f"EXIT_CODE: {proc.returncode}",
                "",
                "STDOUT:",
                proc.stdout or "",
                "",
                "STDERR:",
                proc.stderr or "",
            ]
        ),
        encoding="utf-8",
    )

    success = proc.returncode == 0

    results = _load_json(run_dir / "tournament_results.json") or {}
    health = _load_json(run_dir / "tournament_results_selection_health_dashboard.json") or {}
    transcript = _load_json(run_dir / "tournament_results_transcript.json")
    ledger = _load_json(run_dir / "tournament_results_ledger.json")

    trace_count = 0
    trace_tier = "tier_c"
    if transcript:
        gate_passes = _infer_gate_passes_from_exit_code(
            exit_code=proc.returncode,
            gate_variance_enabled=gate_variance,
            gate_calibration_enabled=gate_calibration,
        )
        trace_tier = assign_trace_quality_tier(
            run_metadata={"runtime_fingerprint": {"strict_runtime": not args.allow_stub}},
            gate_summary={
                "judge_variance_pass": gate_passes["judge_variance_pass"],
                "judge_calibration_pass": gate_passes["judge_calibration_pass"],
                "gates_pass": success,
            },
        )
        traces = normalize_transcript_to_traces(
            transcript=transcript,
            ledger=ledger,
            run_id=batch_id,
            seed=seed,
            judge_model=judge_model,
            judge_reliability_tier=trace_tier,
        )
        export_trace_jsonl(traces, str(run_dir / "trace_records.jsonl"))
        trace_count = len(traces)

    record = {
        "run_no": run_no,
        "seed": seed,
        "run_dir": str(run_dir),
        "started_at": started_at,
        "ended_at": ended_at,
        "exit_code": proc.returncode,
        "success": success,
        "winner": results.get("final_balances", {}) and max(
            results.get("final_balances", {}).items(), key=lambda kv: kv[1]
        )[0]
        if results.get("final_balances")
        else None,
        "rounds_completed": len(results.get("rounds", [])) if results.get("rounds") else 0,
        "eliminated": results.get("eliminated"),
        "health_score": health.get("health_score"),
        "pass_rate": health.get("pass_rate"),
        "aggression_rate": health.get("aggression_rate"),
        "adaptation_gain_after_loss": health.get("adaptation_gain_after_loss"),
        "trace_count": trace_count,
        "trace_quality_tier": trace_tier,
        "endpoint": openai_base_url,
        "artifact_paths": {
            "results_json": str(run_dir / "tournament_results.json"),
            "transcript_json": str(run_dir / "tournament_results_transcript.json"),
            "ledger_json": str(run_dir / "tournament_results_ledger.json"),
            "health_json": str(run_dir / "tournament_results_selection_health_dashboard.json"),
            "trace_jsonl": str(run_dir / "trace_records.jsonl"),
            "run_log": str(run_dir / "run.log"),
        },
    }

    with write_lock:
        _append_jsonl(summary_jsonl, record)
        print(
            f"[batch] run={run_no:03d}/{args.runs} seed={seed} success={success} "
            f"rounds={record['rounds_completed']} traces={trace_count} tier={trace_tier} "
            f"endpoint={openai_base_url or 'default'}"
        )

    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch tournament runner with per-run artifact archival")
    parser.add_argument("--config", default="configs/ollama_tournament_recommended.yaml")
    parser.add_argument("--runs", type=int, default=10, help="Number of tournaments to run")
    parser.add_argument("--start-seed", type=int, default=101, help="Seed for first run")
    parser.add_argument("--seed-step", type=int, default=1, help="Increment between run seeds")
    parser.add_argument("--output-root", default="logs/tournament_batches")
    parser.add_argument("--batch-id", default=None, help="Optional custom batch ID")
    parser.add_argument("--resume", action="store_true", help="Resume existing batch by scheduling only missing run_no values")
    parser.add_argument("--allow-stub", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Pause between runs (not precise when parallel)")
    parser.add_argument("--max-failures", type=int, default=0, help="Stop scheduling new runs once failures exceed this count")

    parser.add_argument("--concurrency", type=int, default=1, help="Number of concurrent tournament runs")
    parser.add_argument(
        "--openai-base-urls",
        default="",
        help="Comma-separated API endpoints for parallel sharding (openai-compatible and vLLM).",
    )

    parser.add_argument("--no-gate-judge-variance", action="store_true")
    parser.add_argument("--variance-runs", type=int, default=10)
    parser.add_argument("--max-judge-stdev", type=float, default=0.05)
    parser.add_argument("--min-judge-mean-a", type=float, default=0.55)

    parser.add_argument("--no-gate-judge-calibration", action="store_true")
    parser.add_argument("--min-calibration-pass-rate", type=float, default=0.67)
    args = parser.parse_args()

    if args.runs <= 0:
        raise ValueError("--runs must be > 0")

    gate_variance = not args.no_gate_judge_variance
    gate_calibration = not args.no_gate_judge_calibration

    batch_id = args.batch_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_root = Path(args.output_root) / batch_id
    batch_root.mkdir(parents=True, exist_ok=True)
    summary_jsonl = batch_root / "batch_summary.jsonl"
    checkpoint_path = batch_root / CHECKPOINT_FILENAME

    tc = load_config(args.config)
    judge_model = tc.judges[0].model if tc.judges else "unknown_judge"
    configured_model_ids = [getattr(d, "model", "") for d in getattr(tc, "debaters", [])] + [judge_model]
    endpoint_env = {
        "openai": any(_is_model_prefix(mid, "openai") for mid in configured_model_ids),
        "vllm": any(_is_model_prefix(mid, "vllm") for mid in configured_model_ids),
        "ollama": any(_is_model_prefix(mid, "ollama") for mid in configured_model_ids),
    }
    setattr(args, "_endpoint_env", endpoint_env)

    base_urls = [u.strip() for u in args.openai_base_urls.split(",") if u.strip()]
    config_fp = _config_fingerprint(args, base_urls)
    if args.resume:
        checkpoint = _load_checkpoint(checkpoint_path)
        _assert_resume_compatible(checkpoint, config_fp)
    else:
        _atomic_write_json(
            checkpoint_path,
            build_batch_checkpoint_payload(batch_id=batch_id, config_fingerprint=config_fp),
        )

    print(f"[batch] id={batch_id} runs={args.runs} config={args.config}")
    print(f"[batch] output={batch_root}")
    print(f"[batch] gates: variance={gate_variance} calibration={gate_calibration}")
    print(f"[batch] concurrency={args.concurrency} endpoints={len(base_urls)}")
    if base_urls and not any(endpoint_env.values()):
        print("[batch][warn] endpoint roster provided but config models are not openai:/vllm:/ollama:")

    records: List[Dict[str, Any]] = []
    failures = 0
    write_lock = threading.Lock()

    skip_run_nos: set[int] = set()
    if args.resume:
        existing_records = _load_summary_records(summary_jsonl)
        existing_by_run = _index_records_by_run_no(existing_records, args.runs)
        records = [existing_by_run[run_no] for run_no in sorted(existing_by_run)]
        skip_run_nos = set(existing_by_run.keys())
        # Normalize checkpoint file to one deduped row per run_no before appending new rows.
        _atomic_write_jsonl_records(summary_jsonl, records)
        print(
            f"[batch] resume enabled: existing_runs={len(skip_run_nos)} "
            f"missing_runs={args.runs - len(skip_run_nos)}"
        )
    elif summary_jsonl.exists():
        # Non-resume mode always starts a fresh summary for deterministic reruns.
        _atomic_write_jsonl_records(summary_jsonl, [])

    jobs = _build_jobs(
        runs=args.runs,
        start_seed=args.start_seed,
        seed_step=args.seed_step,
        base_urls=base_urls,
        skip_run_nos=skip_run_nos,
    )

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        jobs_iter = iter(jobs)
        futures: Dict[Any, tuple[int, int, Optional[str]]] = {}

        def _submit_until_full() -> None:
            while len(futures) < max(1, args.concurrency):
                if args.max_failures > 0 and failures > args.max_failures:
                    return
                try:
                    run_no, seed, endpoint = next(jobs_iter)
                except StopIteration:
                    return
                fut = executor.submit(
                    _run_tournament_job,
                    run_no,
                    seed,
                    batch_root,
                    batch_id,
                    args,
                    gate_variance,
                    gate_calibration,
                    judge_model,
                    summary_jsonl,
                    write_lock,
                    endpoint,
                )
                futures[fut] = (run_no, seed, endpoint)
                if args.sleep_seconds > 0:
                    time.sleep(args.sleep_seconds)

        _submit_until_full()
        while futures:
            fut = next(as_completed(list(futures.keys())))
            run_no, seed, endpoint = futures.pop(fut)
            try:
                record = fut.result()
            except Exception as e:
                failures += 1
                print(f"[batch] job threw exception: run={run_no} seed={seed} err={e}")
                record = _build_exception_record(run_no, seed, endpoint, str(e))
                with write_lock:
                    _append_jsonl(summary_jsonl, record)
            records.append(record)
            if not record.get("success", False):
                failures += 1 if record.get("exit_code") != 9 else 0
            if args.max_failures > 0 and failures > args.max_failures:
                print(f"[batch] stopping early: failures={failures} > max_failures={args.max_failures}")
                continue
            _submit_until_full()

    # Re-sort records by run_no for the manifest array
    records.sort(key=lambda r: r.get("run_no", 999999))
    _atomic_write_jsonl_records(summary_jsonl, records)

    success_records = [r for r in records if r.get("success")]
    winner_counts = Counter(r.get("winner") for r in success_records if r.get("winner"))
    aggregate = {
        "runs_attempted": len(records),
        "runs_requested": args.runs,
        "success_count": len(success_records),
        "failure_count": len(records) - len(success_records),
        "mean_rounds_completed": round(_mean([float(r.get("rounds_completed", 0)) for r in success_records]), 3),
        "mean_health_score": round(
            _mean([float(r["health_score"]) for r in success_records if r.get("health_score") is not None]),
            4,
        ),
        "mean_trace_count": round(_mean([float(r.get("trace_count", 0)) for r in success_records]), 2),
        "winner_counts": dict(winner_counts),
    }

    manifest = {
        "checkpoint_schema_version": CHECKPOINT_SCHEMA_VERSION,
        "config_fingerprint": config_fp,
        "batch_id": batch_id,
        "config": args.config,
        "judge_model": judge_model,
        "allow_stub": args.allow_stub,
        "resume": bool(args.resume),
        "gates": {
            "variance": gate_variance,
            "calibration": gate_calibration,
            "variance_runs": args.variance_runs,
            "max_judge_stdev": args.max_judge_stdev,
            "min_judge_mean_a": args.min_judge_mean_a,
            "min_calibration_pass_rate": args.min_calibration_pass_rate,
        },
        "schedule": {
            "runs": args.runs,
            "start_seed": args.start_seed,
            "seed_step": args.seed_step,
            "sleep_seconds": args.sleep_seconds,
            "concurrency": args.concurrency,
            "openai_base_urls": base_urls,
        },
        "aggregate": aggregate,
        "records": records,
    }
    _atomic_write_json(batch_root / "batch_manifest.json", manifest)

    print(f"[batch] wrote: {summary_jsonl}")
    print(f"[batch] wrote: {batch_root / 'batch_manifest.json'}")
    return 0 if len(success_records) == len(records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
