#!/usr/bin/env python3
"""Run many strict tournament jobs and archive per-run dataset artifacts."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.analysis import assign_trace_quality_tier, export_trace_jsonl, normalize_transcript_to_traces
from src.config_loader import load_config


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _mean(values: List[float]) -> float:
    return (sum(values) / len(values)) if values else 0.0


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch tournament runner with per-run artifact archival")
    parser.add_argument("--config", default="configs/ollama_tournament_recommended.yaml")
    parser.add_argument("--runs", type=int, default=10, help="Number of tournaments to run")
    parser.add_argument("--start-seed", type=int, default=101, help="Seed for first run")
    parser.add_argument("--seed-step", type=int, default=1, help="Increment between run seeds")
    parser.add_argument("--output-root", default="logs/tournament_batches")
    parser.add_argument("--batch-id", default=None, help="Optional custom batch ID")
    parser.add_argument("--allow-stub", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Pause between runs")
    parser.add_argument("--max-failures", type=int, default=0, help="Stop once failures exceed this count")

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

    tc = load_config(args.config)
    judge_model = tc.judges[0].model if tc.judges else "unknown_judge"

    print(f"[batch] id={batch_id} runs={args.runs} config={args.config}")
    print(f"[batch] output={batch_root}")
    print(f"[batch] gates: variance={gate_variance} calibration={gate_calibration}")

    records: List[Dict[str, Any]] = []
    failures = 0

    for idx in range(args.runs):
        run_no = idx + 1
        seed = args.start_seed + idx * args.seed_step
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

        started_at = datetime.now(timezone.utc).isoformat()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        ended_at = datetime.now(timezone.utc).isoformat()

        (run_dir / "run.log").write_text(
            "\n".join(
                [
                    f"CMD: {' '.join(cmd)}",
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
        if not success:
            failures += 1

        results = _load_json(run_dir / "tournament_results.json") or {}
        health = _load_json(run_dir / "tournament_results_selection_health_dashboard.json") or {}
        transcript = _load_json(run_dir / "tournament_results_transcript.json")
        ledger = _load_json(run_dir / "tournament_results_ledger.json")

        trace_count = 0
        trace_tier = "tier_c"
        if transcript:
            trace_tier = assign_trace_quality_tier(
                run_metadata={"runtime_fingerprint": {"strict_runtime": not args.allow_stub}},
                gate_summary={
                    "judge_variance_pass": gate_variance and success,
                    "judge_calibration_pass": gate_calibration and success,
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
            "rounds_completed": len(results.get("rounds", [])),
            "eliminated": results.get("eliminated"),
            "health_score": health.get("health_score"),
            "pass_rate": health.get("pass_rate"),
            "aggression_rate": health.get("aggression_rate"),
            "adaptation_gain_after_loss": health.get("adaptation_gain_after_loss"),
            "trace_count": trace_count,
            "trace_quality_tier": trace_tier,
            "artifact_paths": {
                "results_json": str(run_dir / "tournament_results.json"),
                "transcript_json": str(run_dir / "tournament_results_transcript.json"),
                "ledger_json": str(run_dir / "tournament_results_ledger.json"),
                "health_json": str(run_dir / "tournament_results_selection_health_dashboard.json"),
                "trace_jsonl": str(run_dir / "trace_records.jsonl"),
                "run_log": str(run_dir / "run.log"),
            },
        }

        records.append(record)
        _append_jsonl(summary_jsonl, record)
        print(
            f"[batch] run={run_no:03d}/{args.runs} seed={seed} success={success} "
            f"rounds={record['rounds_completed']} traces={trace_count} tier={trace_tier}"
        )

        if failures > args.max_failures:
            print(f"[batch] stopping early: failures={failures} > max_failures={args.max_failures}")
            break
        if args.sleep_seconds > 0 and run_no < args.runs:
            time.sleep(args.sleep_seconds)

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
        "batch_id": batch_id,
        "config": args.config,
        "judge_model": judge_model,
        "allow_stub": args.allow_stub,
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
        },
        "aggregate": aggregate,
        "records": records,
    }
    (batch_root / "batch_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"[batch] wrote: {summary_jsonl}")
    print(f"[batch] wrote: {batch_root / 'batch_manifest.json'}")
    return 0 if len(success_records) == len(records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
