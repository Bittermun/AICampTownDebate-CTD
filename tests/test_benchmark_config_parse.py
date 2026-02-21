#!/usr/bin/env python3
"""Tests for benchmark policy config parsing."""
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark.config_models import load_benchmark_policy


def test_load_valid_policy():
    policy = load_benchmark_policy("configs/benchmark_phase1.yaml")
    assert policy.meta.benchmark_id == "phase1_truth_reasoning_2026q1"
    assert policy.runtime.judge_gates.variance.runs == 10
    assert "truth_core" in policy.benchmark_groups
    assert "net_roi" in policy.benchmark_groups["economy_adaptation"].metric_transforms
    assert policy.trajectory_checks.enabled is True
    assert policy.runtime.allow_live_source_fallback is True
    assert policy.benchmark_groups["truth_core"].datasets[0].hf_dataset_id == "TIGER-Lab/MMLU-Pro"


def test_missing_required_field_raises():
    broken = """
runtime:
  strict_mode_required: true
"""
    td = Path("logs/test_tmp_config")
    td.mkdir(parents=True, exist_ok=True)
    p = td / "broken.yaml"
    p.write_text(broken, encoding="utf-8")
    try:
        load_benchmark_policy(str(p))
        raise AssertionError("Expected ValueError for missing required fields.")
    except ValueError as e:
        assert "Missing required benchmark config field" in str(e)


if __name__ == "__main__":
    test_load_valid_policy()
    test_missing_required_field_raises()
    print("test_benchmark_config_parse: PASS")
