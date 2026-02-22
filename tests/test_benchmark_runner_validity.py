#!/usr/bin/env python3
"""Tests run validity checks in phase-1 benchmark runner."""
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


def test_missing_required_artifact_marks_invalid():
    policy = load_benchmark_policy("configs/benchmark_phase1.yaml")
    _disable_live_sources(policy)
    policy.invariants.run_validity.required_artifacts.append("nonexistent_artifact")
    policy.trajectory_checks.enabled = False

    td = Path("logs/test_tmp_runner")
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
    assert result.valid_run is False
    assert any("Missing required artifact" in issue for issue in result.validity_issues)


if __name__ == "__main__":
    test_missing_required_artifact_marks_invalid()
    print("test_benchmark_runner_validity: PASS")
