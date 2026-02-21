"""Scoring utilities for benchmark groups and aggregate."""
from __future__ import annotations

from statistics import mean, pstdev
from typing import Dict, List

from .config_models import AggregatePolicy, GroupPolicy, MetricTransformSpec
from .types import AggregateScoreResult, BenchmarkItem, GroupScoreResult


def _apply_transform(value: float, spec: MetricTransformSpec) -> float:
    if spec.type == "identity":
        return value
    if spec.type == "clipped_linear":
        lo = -1.0 if spec.min is None else float(spec.min)
        hi = 1.0 if spec.max is None else float(spec.max)
        if hi <= lo:
            return 0.0
        clipped = min(hi, max(lo, value))
        return (clipped - lo) / (hi - lo)
    return value


def score_group(group_name: str, items: List[BenchmarkItem], policy: GroupPolicy, degraded_mode: bool) -> GroupScoreResult:
    metrics = []
    if policy.metric:
        metrics = [policy.metric]
    elif policy.metrics:
        metrics = policy.metrics

    metric_means_raw: Dict[str, float] = {}
    metric_means_transformed: Dict[str, float] = {}
    reasons: List[str] = []
    for metric in metrics:
        values = [it.metric_values.get(metric) for it in items if metric in it.metric_values]
        raw_mean = float(mean(values)) if values else 0.0
        metric_means_raw[metric] = raw_mean
        transform = policy.metric_transforms.get(metric, MetricTransformSpec(type="identity"))
        metric_means_transformed[metric] = _apply_transform(raw_mean, transform)
        if not values:
            reasons.append(f"Metric '{metric}' missing on all items.")

    if metric_means_transformed:
        score = float(mean(metric_means_transformed.values()))
    else:
        score = 0.0
        reasons.append("No scoring metrics configured.")

    pass_group = score >= policy.min_group_score
    if not pass_group:
        reasons.append(f"Group score {score:.3f} < min_group_score {policy.min_group_score:.3f}")

    if policy.thresholds:
        t = policy.thresholds
        if t.min_mean_roi is not None:
            roi = metric_means_raw.get("net_roi", 0.0)
            if roi < t.min_mean_roi:
                pass_group = False
                reasons.append(f"net_roi {roi:.3f} < threshold {t.min_mean_roi:.3f}")
        if t.min_adaptation_gain_after_loss is not None:
            adapt = metric_means_raw.get("adaptation_gain_after_loss", 0.0)
            if adapt < t.min_adaptation_gain_after_loss:
                pass_group = False
                reasons.append(
                    "adaptation_gain_after_loss "
                    f"{adapt:.3f} < threshold {t.min_adaptation_gain_after_loss:.3f}"
                )
        if t.min_health_score is not None:
            health = metric_means_raw.get("selection_health_score", 0.0)
            if health < t.min_health_score:
                pass_group = False
                reasons.append(f"selection_health_score {health:.3f} < threshold {t.min_health_score:.3f}")

    return GroupScoreResult(
        group_name=group_name,
        score=round(score, 6),
        metric_means={k: round(v, 6) for k, v in metric_means_transformed.items()},
        metric_means_raw={k: round(v, 6) for k, v in metric_means_raw.items()},
        metric_means_transformed={k: round(v, 6) for k, v in metric_means_transformed.items()},
        pass_group=pass_group,
        reasons=reasons,
        item_count=len(items),
        degraded_mode=degraded_mode,
    )


def weighted_group_scores(group_results: Dict[str, GroupScoreResult], group_weights: Dict[str, float]) -> float:
    numerator = 0.0
    denominator = 0.0
    for group_name, res in group_results.items():
        w = float(group_weights.get(group_name, 0.0))
        numerator += res.score * w
        denominator += w
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def score_aggregate(
    seed_aggregate_scores: List[float],
    seed_pass_flags: List[bool],
    policy: AggregatePolicy,
) -> AggregateScoreResult:
    avg = float(mean(seed_aggregate_scores)) if seed_aggregate_scores else 0.0
    stdev = float(pstdev(seed_aggregate_scores)) if len(seed_aggregate_scores) > 1 else 0.0
    benchmark_pass = avg >= policy.min_pass_score
    stability_pass = stdev <= policy.stability_requirements.max_seed_stdev

    directional_consistency = True
    if policy.stability_requirements.require_directional_consistency_across_seeds and seed_pass_flags:
        directional_consistency = all(seed_pass_flags) or not any(seed_pass_flags)

    return AggregateScoreResult(
        aggregate_score_mean=round(avg, 6),
        aggregate_score_stdev=round(stdev, 6),
        benchmark_pass=benchmark_pass,
        stability_pass=stability_pass,
        directional_consistency=directional_consistency,
    )
