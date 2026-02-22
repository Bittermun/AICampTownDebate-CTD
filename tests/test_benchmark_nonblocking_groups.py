#!/usr/bin/env python3
"""Tests non-blocking benchmark group semantics."""
from pathlib import Path
import sys
import yaml

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark.config_models import load_benchmark_policy
from src.benchmark.runner import run_phase1


def _disable_live_sources(policy) -> None:
    for group in policy.benchmark_groups.values():
        for ds in group.datasets:
            ds.hf_dataset_id = None
            ds.hf_subset = None


def test_non_blocking_group_failure_does_not_fail_score_pass():
    policy = load_benchmark_policy("configs/benchmark_phase1.yaml")
    _disable_live_sources(policy)
    policy.trajectory_checks.enabled = False
    policy.runtime.judge_gates.variance.enabled = False
    policy.runtime.judge_gates.calibration.enabled = False
    policy.aggregate_scoring.min_pass_score = 0.5

    # Force the stretch group to fail while keeping it non-blocking.
    policy.benchmark_groups["truth_core_stretch"].min_group_score = 0.99
    policy.benchmark_groups["truth_core_stretch"].weight = 0.0
    policy.benchmark_groups["truth_core_stretch"].blocking = False

    td = Path("logs/test_tmp_nonblocking")
    td.mkdir(parents=True, exist_ok=True)
    tcfg = yaml.safe_load(Path("configs/tournament_config.yaml").read_text(encoding="utf-8"))
    tcfg["models"]["debaters"][0]["model"] = "stub"
    tcfg["models"]["debaters"][1]["model"] = "stub"
    tcfg["models"]["judges"][0]["model"] = "stub"
    tcfg["rounds"]["num_rounds"] = 1
    tcfg["rounds"]["max_iterations"] = 1
    tcfg_path = td / "tournament_test.yaml"
    tcfg_path.write_text(yaml.safe_dump(tcfg, sort_keys=False), encoding="utf-8")

    result = run_phase1(
        policy=policy,
        tournament_config_path=str(tcfg_path),
        model_name="stub",
        judge_model_override="stub",
        seeds=[101],
        fixtures_dir="benchmarks/fixtures",
        allow_stub=True,
    )

    stretch = result.seed_results[0].group_results["truth_core_stretch"]
    assert stretch.pass_group is False
    assert result.benchmark_score_pass is True


if __name__ == "__main__":
    test_non_blocking_group_failure_does_not_fail_score_pass()
    print("test_benchmark_nonblocking_groups: PASS")
