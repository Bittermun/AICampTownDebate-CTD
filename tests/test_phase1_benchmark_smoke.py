#!/usr/bin/env python3
"""Smoke test for CLI phase-1 benchmark runner."""
import json
import subprocess
import sys
from pathlib import Path

import yaml


def test_smoke_cli():
    td_path = Path("logs/test_tmp_smoke")
    td_path.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load(Path("configs/benchmark_phase1.yaml").read_text(encoding="utf-8"))
    cfg["runtime"]["allow_stub_for_research"] = True
    cfg["runtime"]["judge_gates"]["calibration"]["min_pass_rate"] = 0.66
    cfg["trajectory_checks"]["enabled"] = False
    cfg["reporting"]["output_paths"]["benchmark_summary"] = str(td_path / "benchmark_summary.json")
    cfg["reporting"]["output_paths"]["champion_registry"] = str(td_path / "champion_registry.json")

    cfg_path = td_path / "benchmark_test.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    tcfg = yaml.safe_load(Path("configs/tournament_config.yaml").read_text(encoding="utf-8"))
    tcfg["models"]["debaters"][0]["model"] = "stub"
    tcfg["models"]["debaters"][1]["model"] = "stub"
    tcfg["models"]["judges"][0]["model"] = "stub"
    tcfg["rounds"]["num_rounds"] = 1
    tcfg["rounds"]["max_iterations"] = 1
    tcfg_path = td_path / "tournament_test.yaml"
    tcfg_path.write_text(yaml.safe_dump(tcfg, sort_keys=False), encoding="utf-8")

    cmd = [
        sys.executable,
        "tests/run_phase1_benchmark.py",
        "--config",
        str(cfg_path),
        "--tournament-config",
        str(tcfg_path),
        "--model-id",
        "stub",
        "--judge-model",
        "stub",
        "--seeds",
        "101",
        "--allow-stub",
        "--offline-fixtures-dir",
        "benchmarks/fixtures",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode in (0, 2), proc.stdout + "\n" + proc.stderr

    summary_path = Path(cfg["reporting"]["output_paths"]["benchmark_summary"])
    registry_path = Path(cfg["reporting"]["output_paths"]["champion_registry"])
    assert summary_path.exists()
    assert registry_path.exists()

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert "benchmark_id" in payload
    assert "aggregate_score" in payload
    assert "seed_results" in payload


if __name__ == "__main__":
    test_smoke_cli()
    print("test_phase1_benchmark_smoke: PASS")
