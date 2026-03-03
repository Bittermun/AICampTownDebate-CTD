#!/usr/bin/env python3
"""Run an evolutionary benchmark campaign for debate policy search."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark import load_benchmark_policy
from src.evolution import run_evolution_campaign


def _parse_seeds(raw: str | None, default: list[int]) -> list[int]:
    if not raw:
        return default
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Evolutionary search on benchmark fitness")
    parser.add_argument("--benchmark-config", default="configs/benchmark_phase1.yaml")
    parser.add_argument("--tournament-config", default="configs/ollama_tournament_recommended.yaml")
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--seeds", default=None, help="Comma-separated seed override, e.g. 101,202")
    parser.add_argument("--fixtures-dir", default="benchmarks/fixtures")
    parser.add_argument("--generations", type=int, default=3)
    parser.add_argument("--population-size", type=int, default=6)
    parser.add_argument("--elite-count", type=int, default=2)
    parser.add_argument("--mutation-power", type=float, default=1.0)
    parser.add_argument("--rng-seed", type=int, default=17)
    parser.add_argument("--allow-stub", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--source-mode",
        default="default",
        choices=["default", "core_live_stretch_fixture", "all_live", "all_fixture"],
    )
    parser.add_argument("--enable-model-derived-metrics", action="store_true")
    parser.add_argument("--num-rounds-override", type=int, default=None)
    parser.add_argument("--max-iterations-override", type=int, default=None)
    parser.add_argument("--judge-variance-runs-override", type=int, default=None)
    parser.add_argument("--judge-calibration-min-pass-rate-override", type=float, default=None)
    parser.add_argument("--disable-judge-variance-gate", action="store_true")
    parser.add_argument("--disable-judge-calibration-gate", action="store_true")
    parser.add_argument("--output-dir", default="logs")
    args = parser.parse_args()

    policy = load_benchmark_policy(args.benchmark_config)
    seeds = _parse_seeds(args.seeds, policy.meta.seed_policy.seeds)

    report = run_evolution_campaign(
        policy=policy,
        base_tournament_config_path=args.tournament_config,
        model_id=args.model_id,
        judge_model=args.judge_model,
        generations=args.generations,
        population_size=args.population_size,
        elite_count=args.elite_count,
        mutation_power=args.mutation_power,
        rng_seed=args.rng_seed,
        seeds=seeds,
        fixtures_dir=args.fixtures_dir,
        allow_stub=args.allow_stub,
        dry_run=args.dry_run,
        source_mode=args.source_mode,
        enable_model_derived_metrics=args.enable_model_derived_metrics,
        num_rounds_override=args.num_rounds_override,
        max_iterations_override=args.max_iterations_override,
        judge_variance_runs_override=args.judge_variance_runs_override,
        judge_calibration_min_pass_rate_override=args.judge_calibration_min_pass_rate_override,
        disable_judge_variance_gate=args.disable_judge_variance_gate,
        disable_judge_calibration_gate=args.disable_judge_calibration_gate,
        output_dir=args.output_dir,
    )

    print(f"Campaign report: {report['campaign_dir']}")
    print(f"Best candidate config: {report['best_candidate_config']}")
    print(
        "Best candidate metrics: "
        f"fitness={report['best_candidate']['fitness']:.3f} "
        f"aggregate={report['best_candidate']['aggregate_score']:.3f} "
        f"win_rate={report['best_candidate']['win_rate_vs_incumbent']:.3f}"
    )
    print(json.dumps(report["best_candidate"]["profile"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
