#!/usr/bin/env python3
"""Tests for live source failure policy behavior."""
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark.config_models import DatasetSpec, GroupPolicy
from src.benchmark.datasets import HFDatasetAdapter, OfflineFixtureAdapter
from src.benchmark.runner import _evaluate_group


def _make_group_policy() -> GroupPolicy:
    return GroupPolicy(
        weight=1.0,
        datasets=[
            DatasetSpec(
                name="MMLU-Pro",
                source="external",
                split="test",
                sample_size=1,
                hf_dataset_id="org/boom",
                column_mapping={"prompt": "question"},
            )
        ],
        metric="accuracy",
        min_group_score=0.0,
    )


def test_live_failure_fallback_enabled_uses_fixture():
    fixture_adapter = OfflineFixtureAdapter("benchmarks/fixtures")
    spec = _make_group_policy().datasets[0]
    hf_adapter = HFDatasetAdapter(dataset_specs={("truth_core", "MMLU-Pro"): spec}, cache_dir="logs/test_tmp_live_policy")
    hf_adapter.load = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("hf down"))  # type: ignore[method-assign]

    failures = []
    res = _evaluate_group(
        fixture_adapter=fixture_adapter,
        hf_adapter=hf_adapter,
        group_name="truth_core",
        group_policy=_make_group_policy(),
        seed=101,
        strict_runtime=False,
        allow_live_source_fallback=True,
        live_source_failures=failures,
    )
    assert res.degraded_mode is True
    assert len(failures) == 1
    assert "live pull failed" in " ".join(res.reasons)


def test_live_failure_strict_runtime_raises():
    fixture_adapter = OfflineFixtureAdapter("benchmarks/fixtures")
    spec = _make_group_policy().datasets[0]
    hf_adapter = HFDatasetAdapter(dataset_specs={("truth_core", "MMLU-Pro"): spec}, cache_dir="logs/test_tmp_live_policy")
    hf_adapter.load = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("hf down"))  # type: ignore[method-assign]

    try:
        _evaluate_group(
            fixture_adapter=fixture_adapter,
            hf_adapter=hf_adapter,
            group_name="truth_core",
            group_policy=_make_group_policy(),
            seed=101,
            strict_runtime=True,
            allow_live_source_fallback=True,
            live_source_failures=[],
        )
        raise AssertionError("Expected strict runtime live failure to raise")
    except RuntimeError as exc:
        assert "Live dataset pull failed" in str(exc)


def test_live_failure_fallback_disabled_raises():
    fixture_adapter = OfflineFixtureAdapter("benchmarks/fixtures")
    spec = _make_group_policy().datasets[0]
    hf_adapter = HFDatasetAdapter(dataset_specs={("truth_core", "MMLU-Pro"): spec}, cache_dir="logs/test_tmp_live_policy")
    hf_adapter.load = lambda **kwargs: (_ for _ in ()).throw(RuntimeError("hf down"))  # type: ignore[method-assign]

    try:
        _evaluate_group(
            fixture_adapter=fixture_adapter,
            hf_adapter=hf_adapter,
            group_name="truth_core",
            group_policy=_make_group_policy(),
            seed=101,
            strict_runtime=False,
            allow_live_source_fallback=False,
            live_source_failures=[],
        )
        raise AssertionError("Expected non-fallback live failure to raise")
    except RuntimeError as exc:
        assert "Live dataset pull failed" in str(exc)


if __name__ == "__main__":
    test_live_failure_fallback_enabled_uses_fixture()
    test_live_failure_strict_runtime_raises()
    test_live_failure_fallback_disabled_raises()
    print("test_benchmark_live_failure_policy: PASS")
