#!/usr/bin/env python3
"""Tests for benchmark policy config parsing."""
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark.config_models import load_benchmark_policy
from src.config_loader import load_config


def test_load_valid_policy():
    policy = load_benchmark_policy("configs/benchmark_phase1.yaml")
    assert policy.meta.benchmark_id == "phase1_truth_reasoning_2026q1"
    assert policy.runtime.judge_gates.variance.runs == 10
    assert "truth_core_core" in policy.benchmark_groups
    assert "truth_core_stretch" in policy.benchmark_groups
    assert "net_roi" in policy.benchmark_groups["economy_adaptation"].metric_transforms
    assert policy.trajectory_checks.enabled is True
    assert policy.runtime.allow_live_source_fallback is True
    assert policy.benchmark_groups["truth_core_core"].datasets[0].hf_dataset_id == "TIGER-Lab/MMLU-Pro"


def test_non_blocking_group_parse():
    policy = load_benchmark_policy("configs/benchmark_phase1.yaml")
    assert policy.benchmark_groups["truth_core_core"].blocking is True
    assert policy.benchmark_groups["truth_core_stretch"].blocking is False


def test_tournament_config_debater_knob_defaults():
    cfg = load_config("configs/ollama_tournament_recommended.yaml")
    d0 = cfg.debaters[0]
    assert d0.kelly_enabled is True
    assert d0.kelly_scale == 0.5
    assert d0.kelly_cap == 0.25
    assert d0.verbosity_scale_enabled is True
    assert d0.verbosity_base_tokens == 600
    assert d0.multi_agent_enabled is False
    assert d0.multi_agent_mode == "none"
    assert d0.multi_agent_max_tokens == 160
    assert d0.multi_agent_min_balance == 80.0


def test_multi_agent_experimental_config_parse():
    cfg = load_config("configs/multi_agent_experimental.yaml")
    d0 = cfg.debaters[0]
    d1 = cfg.debaters[1]
    assert d0.multi_agent_enabled is True
    assert d1.multi_agent_enabled is True
    assert d0.multi_agent_mode == "critique"
    assert d1.multi_agent_mode == "synthesize"
    assert d0.multi_agent_max_tokens == 120
    assert d1.multi_agent_max_tokens == 120


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
    test_non_blocking_group_parse()
    test_tournament_config_debater_knob_defaults()
    test_multi_agent_experimental_config_parse()
    test_missing_required_field_raises()
    print("test_benchmark_config_parse: PASS")
