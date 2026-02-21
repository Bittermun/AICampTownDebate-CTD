#!/usr/bin/env python3
"""Tests for benchmark registry updates."""
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark.config_models import load_benchmark_policy
from src.benchmark.registry import update_registry_if_eligible


def test_registry_updates_only_on_valid_pass():
    policy = load_benchmark_policy("configs/benchmark_phase1.yaml")
    registry = {"models": {}, "history": []}

    # Invalid run: should not update ELO.
    reg1, elo1, tier1, notes1 = update_registry_if_eligible(
        registry=registry,
        policy=policy,
        model_name="stub-model",
        judge_name="stub-judge",
        aggregate_score=0.70,
        valid_run=False,
        passed=True,
        metadata={},
    )
    assert elo1["before"] == elo1["after"]
    assert "not updated" in " ".join(notes1).lower()

    # Valid pass: should update ELO.
    reg2, elo2, tier2, _ = update_registry_if_eligible(
        registry=reg1,
        policy=policy,
        model_name="stub-model",
        judge_name="stub-judge",
        aggregate_score=0.70,
        valid_run=True,
        passed=True,
        metadata={"seed_set": [101, 202, 303], "artifact_paths": {}},
    )
    assert elo2["after"] > elo2["before"]
    assert tier2["after"] != ""
    assert reg2["models"]["stub-model"]["matches"] >= 1


if __name__ == "__main__":
    test_registry_updates_only_on_valid_pass()
    print("test_benchmark_registry: PASS")
