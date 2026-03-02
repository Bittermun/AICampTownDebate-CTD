#!/usr/bin/env python3
"""Tests score-source plumbing for model-derived metric overrides."""
import json
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark.config_models import DatasetSpec, GroupPolicy
from src.benchmark.runner import (
    _bootstrap_mean_ci,
    _build_group_metric_overrides_from_artifacts,
    _build_group_metric_overrides_from_health,
    _evaluate_group,
    _extract_multidim_metric_overrides_from_transcript,
    _summarize_counterfactual_scoring,
    _summarize_score_provenance,
)
from src.benchmark.types import BenchmarkItem, GroupScoreResult, SeedResult


class _FixtureAdapter:
    def load(self, group_name: str, dataset_name: str, limit=None):
        items = [
            BenchmarkItem(
                item_id=f"{dataset_name}-1",
                group=group_name,
                dataset=dataset_name,
                prompt="p1",
                metric_values={"selection_health_score": 0.2},
            ),
            BenchmarkItem(
                item_id=f"{dataset_name}-2",
                group=group_name,
                dataset=dataset_name,
                prompt="p2",
                metric_values={"selection_health_score": 0.4},
            ),
        ]
        if limit is not None:
            items = items[: int(limit)]
        return items, False


class _HFAdapter:
    def load(self, group_name: str, dataset_name: str, limit=None):
        raise AssertionError("HF adapter should not be used in this unit test")


class _FixtureAccuracyAdapter:
    def load(self, group_name: str, dataset_name: str, limit=None):
        items = [
            BenchmarkItem(
                item_id=f"{dataset_name}-1",
                group=group_name,
                dataset=dataset_name,
                prompt="p1",
                metric_values={"accuracy": 0.2},
            ),
            BenchmarkItem(
                item_id=f"{dataset_name}-2",
                group=group_name,
                dataset=dataset_name,
                prompt="p2",
                metric_values={"accuracy": 0.4},
            ),
        ]
        if limit is not None:
            items = items[: int(limit)]
        return items, False


def test_health_metric_overrides_map_to_economy_group():
    overrides = _build_group_metric_overrides_from_health(
        {"health_score": 0.77, "adaptation_gain_after_loss": 0.05}
    )
    assert "economy_adaptation" in overrides
    econ = overrides["economy_adaptation"]
    assert econ["selection_health_score"] == 0.77
    assert econ["adaptation_gain_after_loss"] == 0.05


def test_evaluate_group_uses_model_metric_override_with_fixture_fallback():
    fixture_adapter = _FixtureAdapter()
    hf_adapter = _HFAdapter()
    group_policy = GroupPolicy(
        weight=1.0,
        datasets=[DatasetSpec(name="budget_sensitive_internal", source="internal", sample_size=2)],
        metric="selection_health_score",
        min_group_score=0.0,
    )

    baseline = _evaluate_group(
        fixture_adapter=fixture_adapter,
        hf_adapter=hf_adapter,
        group_name="economy_adaptation",
        group_policy=group_policy,
        seed=101,
        strict_runtime=False,
        allow_live_source_fallback=True,
        live_source_failures=[],
    )
    overridden = _evaluate_group(
        fixture_adapter=fixture_adapter,
        hf_adapter=hf_adapter,
        group_name="economy_adaptation",
        group_policy=group_policy,
        seed=101,
        strict_runtime=False,
        allow_live_source_fallback=True,
        live_source_failures=[],
        model_metric_values={"selection_health_score": 0.9},
    )

    assert baseline.score == 0.3
    assert baseline.score_source == "fixture_static"
    assert overridden.score == 0.9
    assert overridden.score_source == "model_derived"
    assert overridden.metric_sources["selection_health_score"] == "model_derived"


def test_extract_multidim_metric_overrides_from_transcript():
    td = Path("logs/test_tmp_score_sources")
    td.mkdir(parents=True, exist_ok=True)
    transcript_path = td / "transcript_with_multidim.json"
    payload = {
        "rounds": [
            {
                "turns": [
                    {"type": "judgment", "content": "ignored early judgment"},
                    {
                        "type": "judgment",
                        "content": (
                            "[MULTI-DIM] Acc: A=70%/B=30%, Resp: A=60%/B=40%, "
                            "Dev: A=80%/B=20% | reason"
                        ),
                    },
                ]
            }
        ]
    }
    transcript_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    overrides = _extract_multidim_metric_overrides_from_transcript(str(transcript_path))
    assert overrides["truth_core_core"]["accuracy"] == 0.7
    assert overrides["truth_core_stretch"]["accuracy"] == 0.7
    assert overrides["reasoning_core"]["task_accuracy"] == 0.7
    assert overrides["reasoning_core"]["evidence_grounding"] == 0.7


def test_build_group_metric_overrides_from_artifacts_merges_sources():
    td = Path("logs/test_tmp_score_sources")
    td.mkdir(parents=True, exist_ok=True)
    transcript_path = td / "transcript_merge_sources.json"
    payload = {
        "rounds": [
            {
                "turns": [
                    {
                        "type": "judgment",
                        "content": (
                            "[MULTI-DIM] Acc: A=65%/B=35%, Resp: A=55%/B=45%, "
                            "Dev: A=75%/B=25% | reason"
                        ),
                    }
                ]
            }
        ]
    }
    transcript_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    overrides = _build_group_metric_overrides_from_artifacts(
        health={"health_score": 0.66, "adaptation_gain_after_loss": 0.04},
        transcript_path=str(transcript_path),
    )
    assert overrides["economy_adaptation"]["selection_health_score"] == 0.66
    assert overrides["economy_adaptation"]["adaptation_gain_after_loss"] == 0.04
    assert overrides["truth_core_core"]["accuracy"] == 0.65
    assert overrides["reasoning_core"]["task_accuracy"] == 0.65


def test_evaluate_group_truth_accuracy_override_changes_score():
    fixture_adapter = _FixtureAccuracyAdapter()
    hf_adapter = _HFAdapter()
    group_policy = GroupPolicy(
        weight=1.0,
        datasets=[DatasetSpec(name="truth_core_sample", source="internal", sample_size=2)],
        metric="accuracy",
        min_group_score=0.0,
    )

    baseline = _evaluate_group(
        fixture_adapter=fixture_adapter,
        hf_adapter=hf_adapter,
        group_name="truth_core_core",
        group_policy=group_policy,
        seed=101,
        strict_runtime=False,
        allow_live_source_fallback=True,
        live_source_failures=[],
    )
    overridden = _evaluate_group(
        fixture_adapter=fixture_adapter,
        hf_adapter=hf_adapter,
        group_name="truth_core_core",
        group_policy=group_policy,
        seed=101,
        strict_runtime=False,
        allow_live_source_fallback=True,
        live_source_failures=[],
        model_metric_values={"accuracy": 0.83},
    )

    assert baseline.score == 0.3
    assert overridden.score == 0.83
    assert overridden.score_source == "model_derived"
    assert overridden.metric_sources["accuracy"] == "model_derived"


def test_summarize_score_provenance_marks_hybrid_aggregate():
    seed1 = SeedResult(
        seed=101,
        group_results={
            "truth_core_core": GroupScoreResult(
                group_name="truth_core_core",
                score=0.6,
                metric_means={"accuracy": 0.6},
                pass_group=True,
                metric_sources={"accuracy": "model_derived"},
                score_source="model_derived",
            ),
            "economy_adaptation": GroupScoreResult(
                group_name="economy_adaptation",
                score=0.5,
                metric_means={"selection_health_score": 0.5},
                pass_group=True,
                metric_sources={"selection_health_score": "fixture_static"},
                score_source="fixture_static",
            ),
        },
        aggregate_score=0.0,
        pass_benchmark=False,
    )
    seed2 = SeedResult(
        seed=202,
        group_results={
            "truth_core_core": GroupScoreResult(
                group_name="truth_core_core",
                score=0.62,
                metric_means={"accuracy": 0.62},
                pass_group=True,
                metric_sources={"accuracy": "model_derived"},
                score_source="model_derived",
            ),
            "economy_adaptation": GroupScoreResult(
                group_name="economy_adaptation",
                score=0.52,
                metric_means={"selection_health_score": 0.52},
                pass_group=True,
                metric_sources={"selection_health_score": "fixture_static"},
                score_source="fixture_static",
            ),
        },
        aggregate_score=0.0,
        pass_benchmark=False,
    )

    provenance = _summarize_score_provenance([seed1, seed2])
    assert provenance["aggregate_score_source"] == "hybrid"
    assert provenance["group_score_sources"]["truth_core_core"] == "model_derived"
    assert provenance["group_score_sources"]["economy_adaptation"] == "fixture_static"


def test_counterfactual_summary_reports_uplift_ci():
    summary = _summarize_counterfactual_scoring(
        fixture_aggregates=[0.5, 0.52, 0.51],
        model_derived_aggregates=[0.56, 0.58, 0.57],
        primary_lane="model_derived",
    )
    uplift = summary["uplift_model_minus_fixture"]
    assert summary["primary_lane"] == "model_derived"
    assert uplift["mean"] > 0.0
    assert uplift["ci95_low"] <= uplift["mean"] <= uplift["ci95_high"]
    assert uplift["n_seeds"] == 3


def test_bootstrap_mean_ci_single_value():
    lo, hi = _bootstrap_mean_ci([0.123], samples=20, alpha=0.05, seed=7)
    assert lo == 0.123
    assert hi == 0.123


if __name__ == "__main__":
    test_health_metric_overrides_map_to_economy_group()
    test_evaluate_group_uses_model_metric_override_with_fixture_fallback()
    test_extract_multidim_metric_overrides_from_transcript()
    test_build_group_metric_overrides_from_artifacts_merges_sources()
    test_evaluate_group_truth_accuracy_override_changes_score()
    test_summarize_score_provenance_marks_hybrid_aggregate()
    test_counterfactual_summary_reports_uplift_ci()
    test_bootstrap_mean_ci_single_value()
    print("test_benchmark_score_sources: PASS")
