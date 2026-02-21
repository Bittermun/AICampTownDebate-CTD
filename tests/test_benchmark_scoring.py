#!/usr/bin/env python3
"""Tests for benchmark scoring math."""
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark.config_models import (
    AggregatePolicy,
    GroupPolicy,
    GroupThresholds,
    MetricTransformSpec,
    StabilityPolicy,
)
from src.benchmark.scoring import score_aggregate, score_group, weighted_group_scores
from src.benchmark.types import BenchmarkItem, GroupScoreResult


def test_group_scoring_and_thresholds():
    policy = GroupPolicy(
        weight=0.2,
        metrics=["net_roi", "adaptation_gain_after_loss", "selection_health_score"],
        metric_transforms={
            "net_roi": MetricTransformSpec(type="clipped_linear", min=-1.0, max=1.0),
            "adaptation_gain_after_loss": MetricTransformSpec(type="clipped_linear", min=-0.05, max=0.10),
        },
        min_group_score=0.5,
        thresholds=GroupThresholds(min_mean_roi=-0.1, min_adaptation_gain_after_loss=0.01, min_health_score=0.55),
    )
    items = [
        BenchmarkItem(
            item_id="1",
            group="economy_adaptation",
            dataset="budget",
            prompt="x",
            metric_values={"net_roi": -0.05, "adaptation_gain_after_loss": 0.02, "selection_health_score": 0.58},
        ),
        BenchmarkItem(
            item_id="2",
            group="economy_adaptation",
            dataset="budget",
            prompt="x",
            metric_values={"net_roi": -0.08, "adaptation_gain_after_loss": 0.03, "selection_health_score": 0.57},
        ),
    ]
    result = score_group("economy_adaptation", items, policy, degraded_mode=False)
    assert result.pass_group is True
    assert result.metric_means_raw["net_roi"] < 0
    assert 0.0 <= result.metric_means_transformed["net_roi"] <= 1.0


def test_weighted_and_aggregate_scoring():
    group_results = {
        "a": GroupScoreResult("a", 0.70, {}, True),
        "b": GroupScoreResult("b", 0.50, {}, True),
    }
    weights = {"a": 0.6, "b": 0.4}
    weighted = weighted_group_scores(group_results, weights)
    assert round(weighted, 3) == 0.62

    agg = score_aggregate(
        seed_aggregate_scores=[0.61, 0.63, 0.62],
        seed_pass_flags=[True, True, True],
        policy=AggregatePolicy(min_pass_score=0.60, stability_requirements=StabilityPolicy(max_seed_stdev=0.02)),
    )
    assert agg.benchmark_pass is True
    assert agg.stability_pass is True
    assert agg.directional_consistency is True


if __name__ == "__main__":
    test_group_scoring_and_thresholds()
    test_weighted_and_aggregate_scoring()
    print("test_benchmark_scoring: PASS")
