#!/usr/bin/env python3
"""Tests run-isolated artifact roots for benchmark executions."""
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


def _make_tournament_cfg(path: Path) -> Path:
    tcfg = yaml.safe_load(Path("configs/tournament_config.yaml").read_text(encoding="utf-8"))
    tcfg["models"]["debaters"][0]["model"] = "stub"
    tcfg["models"]["debaters"][1]["model"] = "stub"
    tcfg["models"]["judges"][0]["model"] = "stub"
    tcfg["rounds"]["num_rounds"] = 1
    tcfg["rounds"]["max_iterations"] = 1
    path.write_text(yaml.safe_dump(tcfg, sort_keys=False), encoding="utf-8")
    return path


def test_artifact_root_isolation():
    policy = load_benchmark_policy("configs/benchmark_phase1.yaml")
    _disable_live_sources(policy)
    policy.trajectory_checks.enabled = False
    policy.runtime.judge_gates.variance.enabled = False
    policy.runtime.judge_gates.calibration.enabled = False

    td = Path("logs/test_tmp_isolation")
    td.mkdir(parents=True, exist_ok=True)
    tcfg_path = _make_tournament_cfg(td / "tournament_test.yaml")

    root_a = td / "run_a"
    root_b = td / "run_b"

    run_phase1(
        policy=policy,
        tournament_config_path=str(tcfg_path),
        model_name="stub",
        judge_model_override="stub",
        seeds=[101],
        fixtures_dir="benchmarks/fixtures",
        allow_stub=True,
        artifact_root=str(root_a),
        run_label="run_a",
    )
    run_phase1(
        policy=policy,
        tournament_config_path=str(tcfg_path),
        model_name="stub",
        judge_model_override="stub",
        seeds=[101],
        fixtures_dir="benchmarks/fixtures",
        allow_stub=True,
        artifact_root=str(root_b),
        run_label="run_b",
    )

    assert (root_a / "benchmark_artifacts" / "seed_101" / "tournament_results.json").exists()
    assert (root_b / "benchmark_artifacts" / "seed_101" / "tournament_results.json").exists()
    assert (root_a / "benchmark_artifacts" / "seed_101" / "tournament_results.json").read_text(encoding="utf-8")
    assert (root_b / "benchmark_artifacts" / "seed_101" / "tournament_results.json").read_text(encoding="utf-8")


if __name__ == "__main__":
    test_artifact_root_isolation()
    print("test_benchmark_artifact_isolation: PASS")

