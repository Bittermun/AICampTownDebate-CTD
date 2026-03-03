#!/usr/bin/env python3
"""Unit tests for evolutionary campaign utilities."""
from pathlib import Path
import random
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.evolution.campaign import (
    StrategyProfile,
    build_candidate_config,
    compute_fitness,
    mutate_profile,
    parse_profile_from_debater_spec,
)


def test_parse_profile_defaults():
    spec = {
        "name": "Alpha",
        "model": "stub",
        "ev_guard_min_ev": -0.07,
        "kelly_scale": 0.62,
    }
    profile = parse_profile_from_debater_spec(spec)
    assert profile.ev_guard_min_ev == -0.07
    assert profile.kelly_scale == 0.62
    assert profile.kelly_cap == 0.25
    assert profile.verbosity_base_tokens == 600


def test_mutate_profile_bounds():
    base = StrategyProfile(
        ev_guard_min_ev=-0.03,
        ev_guard_edge_scale=0.8,
        low_balance_threshold=60.0,
        low_balance_bet_cap=10.0,
        kelly_enabled=True,
        kelly_scale=0.5,
        kelly_cap=0.25,
        verbosity_scale_enabled=True,
        verbosity_base_tokens=600,
        directive_ids=[],
    )
    rng = random.Random(7)
    for _ in range(80):
        m = mutate_profile(base, rng=rng, mutation_power=1.4)
        assert -0.35 <= m.ev_guard_min_ev <= 0.08
        assert 0.2 <= m.ev_guard_edge_scale <= 1.8
        assert 20.0 <= m.low_balance_threshold <= 240.0
        assert 2.0 <= m.low_balance_bet_cap <= 40.0
        assert 0.05 <= m.kelly_scale <= 1.2
        assert 0.05 <= m.kelly_cap <= 0.75
        assert 120 <= m.verbosity_base_tokens <= 1400
        assert len(m.directive_ids) <= 3


def test_build_candidate_config_applies_profile():
    base_cfg = {
        "models": {
            "debaters": [
                {"name": "Alpha", "model": "stub", "system_prompt": "Base A"},
                {"name": "Beta", "model": "stub", "system_prompt": "Base B"},
            ]
        },
        "economy": {"initial_balance": 200},
        "rounds": {"num_rounds": 2, "max_iterations": 2, "topics": ["x"]},
    }
    candidate = StrategyProfile(
        ev_guard_min_ev=-0.1,
        ev_guard_edge_scale=1.1,
        low_balance_threshold=80.0,
        low_balance_bet_cap=7.0,
        kelly_enabled=False,
        kelly_scale=0.3,
        kelly_cap=0.2,
        verbosity_scale_enabled=True,
        verbosity_base_tokens=450,
        directive_ids=["SURVIVAL_FIRST", "ANTI_RAMBLE"],
    )
    incumbent = StrategyProfile(directive_ids=["PRESS_EDGE"])
    built = build_candidate_config(base_cfg, candidate, incumbent)
    d0 = built["models"]["debaters"][0]
    d1 = built["models"]["debaters"][1]
    assert d0["kelly_enabled"] is False
    assert d0["verbosity_base_tokens"] == 450
    assert "EVOLUTIONARY DIRECTIVES" in d0["system_prompt"]
    assert "Base A" in d0["system_prompt"]
    assert d1["kelly_enabled"] is True
    assert "PRESS_EDGE" not in d1["system_prompt"]
    assert "EVOLUTIONARY DIRECTIVES" in d1["system_prompt"]


def test_compute_fitness_penalizes_invalid_runs():
    class DummyRun:
        aggregate_score = 0.6
        trajectory_summary = {
            "mean_entropy_bits": 0.9,
            "mean_adaptation_gain_after_loss": 0.1,
            "mean_pass_shift": 0.0,
        }
        final_pass = False
        gates_pass = False
        valid_run = False
        pass_fail = "fail"

    run = DummyRun()
    fitness = compute_fitness(run, win_rate=0.4, mean_balance_edge=10.0)
    assert fitness < 0.4


if __name__ == "__main__":
    test_parse_profile_defaults()
    test_mutate_profile_bounds()
    test_build_candidate_config_applies_profile()
    test_compute_fitness_penalizes_invalid_runs()
    print("test_evolution_campaign: PASS")
