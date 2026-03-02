#!/usr/bin/env python3
"""Audit fixture-based score ceiling and benchmark passability."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark import load_benchmark_policy  # noqa: E402
from src.benchmark.datasets import OfflineFixtureAdapter  # noqa: E402
from src.benchmark.scoring import score_group, weighted_group_scores  # noqa: E402


def _group_metrics(group_policy) -> List[str]:
    if group_policy.metric:
        return [group_policy.metric]
    return list(group_policy.metrics or [])


def _coverage_ratio(items, metric: str) -> float:
    if not items:
        return 0.0
    have = sum(1 for it in items if metric in it.metric_values)
    return have / len(items)


def build_fixture_audit(config_path: str, fixtures_dir: str) -> Dict[str, Any]:
    policy = load_benchmark_policy(config_path)
    adapter = OfflineFixtureAdapter(fixtures_dir)

    group_results = {}
    group_report: Dict[str, Any] = {}

    for group_name, group_policy in policy.benchmark_groups.items():
        items = []
        degraded = False
        dataset_rows = []

        for ds in group_policy.datasets:
            ds_items, ds_degraded = adapter.load(group_name=group_name, dataset_name=ds.name, limit=None)
            items.extend(ds_items)
            degraded = degraded or ds_degraded

            metrics = _group_metrics(group_policy)
            dataset_rows.append(
                {
                    "dataset": ds.name,
                    "rows": len(ds_items),
                    "metric_coverage": {
                        m: round(_coverage_ratio(ds_items, m), 6) for m in metrics
                    },
                }
            )

        scored = score_group(group_name, items, group_policy, degraded_mode=degraded)
        group_results[group_name] = scored
        group_report[group_name] = {
            "weight": float(group_policy.weight),
            "score": float(scored.score),
            "pass_group": bool(scored.pass_group),
            "metrics": _group_metrics(group_policy),
            "metric_means_raw": dict(scored.metric_means_raw),
            "metric_means_transformed": dict(scored.metric_means_transformed),
            "item_count": int(scored.item_count),
            "degraded_mode": bool(scored.degraded_mode),
            "reasons": list(scored.reasons),
            "datasets": dataset_rows,
        }

    weights = {name: gp.weight for name, gp in policy.benchmark_groups.items()}
    aggregate = float(weighted_group_scores(group_results, weights))
    min_pass = float(policy.aggregate_scoring.min_pass_score)
    delta = aggregate - min_pass

    return {
        "config_path": config_path,
        "fixtures_dir": fixtures_dir,
        "aggregate_fixture_score": round(aggregate, 6),
        "aggregate_min_pass_score": round(min_pass, 6),
        "aggregate_delta_to_pass": round(delta, 6),
        "aggregate_passable_in_fixture_mode": bool(aggregate >= min_pass),
        "all_groups_pass": all(bool(group_report[g]["pass_group"]) for g in group_report),
        "measurement_provenance_note": (
            "Scores in this audit are computed from fixture metric_values; "
            "treat as fixture-static unless proven model-derived elsewhere."
        ),
        "groups": group_report,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit fixture score ceiling and passability")
    parser.add_argument("--config", default="configs/benchmark_phase1.yaml")
    parser.add_argument("--fixtures-dir", default="benchmarks/fixtures")
    parser.add_argument("--output", default=None, help="Optional path to write JSON audit")
    parser.add_argument(
        "--fail-on-unreachable",
        action="store_true",
        help="Exit non-zero when fixture aggregate cannot reach min pass score",
    )
    args = parser.parse_args()

    audit = build_fixture_audit(config_path=args.config, fixtures_dir=args.fixtures_dir)
    print(json.dumps(audit, indent=2))

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(audit, indent=2), encoding="utf-8")
        print(f"[audit] wrote: {out}")

    if args.fail_on_unreachable and not audit["aggregate_passable_in_fixture_mode"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

