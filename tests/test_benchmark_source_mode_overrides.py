#!/usr/bin/env python3
"""Tests for benchmark dataset source mode overrides."""
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark.runner import _dataset_source_mode


def test_source_mode_default():
    assert _dataset_source_mode("default", "truth_core_core", has_hf_dataset=True) == "default"


def test_source_mode_core_live_stretch_fixture():
    assert _dataset_source_mode("core_live_stretch_fixture", "truth_core_core", has_hf_dataset=True) == "live"
    assert _dataset_source_mode("core_live_stretch_fixture", "truth_core_stretch", has_hf_dataset=True) == "fixture"
    assert _dataset_source_mode("core_live_stretch_fixture", "reasoning_core", has_hf_dataset=True) == "default"


def test_source_mode_all_fixture_and_all_live():
    assert _dataset_source_mode("all_fixture", "truth_core_core", has_hf_dataset=True) == "fixture"
    assert _dataset_source_mode("all_live", "truth_core_core", has_hf_dataset=True) == "live"
    assert _dataset_source_mode("all_live", "reasoning_core", has_hf_dataset=False) == "fixture"


if __name__ == "__main__":
    test_source_mode_default()
    test_source_mode_core_live_stretch_fixture()
    test_source_mode_all_fixture_and_all_live()
    print("test_benchmark_source_mode_overrides: PASS")

