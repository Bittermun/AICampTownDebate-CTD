#!/usr/bin/env python3
"""Run benchmark -> submission packet -> training data prep in one command."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark import build_submission_packet  # noqa: E402
from src.training import build_training_data_from_summary  # noqa: E402


def _parse_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _run_benchmark(args, summary_path: Path, registry_path: Path, artifact_root: Path) -> int:
    cmd = [
        sys.executable,
        "tests/run_phase1_benchmark.py",
        "--config",
        args.config,
        "--tournament-config",
        args.tournament_config,
        "--model-id",
        args.model_id,
        "--seeds",
        str(args.seed),
        "--offline-fixtures-dir",
        args.fixtures_dir,
        "--output-summary",
        str(summary_path),
        "--output-registry",
        str(registry_path),
        "--source-mode",
        args.source_mode,
        "--artifact-root",
        str(artifact_root),
        "--run-label",
        args.run_label,
    ]
    if args.judge_model:
        cmd.extend(["--judge-model", args.judge_model])
    if args.allow_stub:
        cmd.append("--allow-stub")
    if args.enable_model_derived_metrics:
        cmd.append("--enable-model-derived-metrics")
    if args.num_rounds_override is not None:
        cmd.extend(["--num-rounds-override", str(args.num_rounds_override)])
    if args.max_iterations_override is not None:
        cmd.extend(["--max-iterations-override", str(args.max_iterations_override)])
    print(f"[smoke] benchmark cmd: {' '.join(cmd)}")
    proc = subprocess.run(cmd, text=True)
    return int(proc.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="End-to-end smoke pipeline for benchmark + packet + training data")
    parser.add_argument("--config", default="configs/benchmark_phase1.yaml")
    parser.add_argument("--tournament-config", default="configs/tournament_config.yaml")
    parser.add_argument("--model-id", default="stub")
    parser.add_argument("--judge-model", default="stub")
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--fixtures-dir", default="benchmarks/fixtures")
    parser.add_argument(
        "--source-mode",
        default="all_fixture",
        choices=["default", "core_live_stretch_fixture", "all_live", "all_fixture"],
    )
    parser.add_argument("--artifact-root", default="logs/smoke_e2e")
    parser.add_argument("--run-label", default="smoke_e2e")
    parser.add_argument("--allow-stub", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--enable-model-derived-metrics", action="store_true")
    parser.add_argument("--num-rounds-override", type=int, default=1)
    parser.add_argument("--max-iterations-override", type=int, default=1)
    parser.add_argument("--min-tier", default="tier_b", choices=["tier_a", "tier_b", "tier_c"])
    parser.add_argument("--include-tiers", default="")
    parser.add_argument("--notes", default="Smoke pipeline dataset prep")
    args = parser.parse_args()

    root = Path(args.artifact_root)
    root.mkdir(parents=True, exist_ok=True)
    summary_path = root / "benchmark_summary.json"
    registry_path = root / "champion_registry.json"
    run_artifacts = root / "run_artifacts"
    packet_dir = root / "submission_packet"
    training_dir = root / "training_data"
    report_path = root / "smoke_pipeline_report.json"

    bench_rc = _run_benchmark(args, summary_path, registry_path, run_artifacts)
    if bench_rc not in {0, 2, 3}:
        print(f"[ERROR] benchmark stage failed with return code {bench_rc}")
        return bench_rc
    if not summary_path.exists():
        print(f"[ERROR] benchmark summary missing: {summary_path}")
        return 4

    try:
        packet_result = build_submission_packet(
            summary_path=str(summary_path),
            output_dir=str(packet_dir),
            run_label=args.run_label,
        )
    except Exception as exc:
        print(f"[ERROR] submission packet stage failed: {exc}")
        return 5

    include_tiers = _parse_csv(args.include_tiers)
    try:
        training_result = build_training_data_from_summary(
            summary_path=str(summary_path),
            output_dir=str(training_dir),
            min_tier=args.min_tier,
            include_tiers=include_tiers,
            notes=args.notes,
        )
    except Exception as exc:
        print(f"[ERROR] training data prep stage failed: {exc}")
        return 6

    report = {
        "benchmark_return_code": bench_rc,
        "benchmark_summary_path": str(summary_path),
        "benchmark_registry_path": str(registry_path),
        "submission_packet": packet_result,
        "training_data": training_result.to_dict(),
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"[smoke] report: {report_path}")
    if bench_rc in {2, 3}:
        print("[smoke] benchmark did not fully pass gates, but pipeline artifact flow succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
