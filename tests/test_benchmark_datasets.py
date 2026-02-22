#!/usr/bin/env python3
"""Unit tests for benchmark dataset adapters."""
from pathlib import Path
import json
import shutil
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark.config_models import DatasetSpec
from src.benchmark.datasets import HFDatasetAdapter


def _clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def test_hf_adapter_mapping_sampling_hash_and_provenance():
    cache_dir = Path("logs/test_tmp_hf_cache")
    _clean_dir(cache_dir)

    spec = DatasetSpec(
        name="TinyTruth",
        source="external",
        split="test",
        hf_dataset_id="org/tiny_truth",
        hf_subset="default",
        column_mapping={
            "id": "qid",
            "prompt": "question",
            "expected": "answer",
            "metric_values": {"accuracy": "acc"},
            "tags": "labels",
            "static_tags": ["external_live"],
        },
    )
    adapter = HFDatasetAdapter(
        dataset_specs={("truth_core", "TinyTruth"): spec},
        cache_dir=str(cache_dir),
    )

    fake_rows = [
        {"qid": "q1", "question": "What is 2+2?", "answer": "4", "acc": 1.0, "labels": ["math"]},
        {"qid": "q2", "question": "Capital of France?", "answer": "Paris", "acc": 0.0, "labels": ["geo"]},
    ]
    adapter._load_hf_split = lambda _spec: ("test", fake_rows)  # type: ignore[method-assign]

    items, degraded = adapter.load(group_name="truth_core", dataset_name="TinyTruth", limit=1)
    assert degraded is False
    assert len(items) == 1
    assert items[0].item_id == "q1"
    assert items[0].prompt == "What is 2+2?"
    assert items[0].expected == "4"
    assert items[0].metric_values["accuracy"] == 1.0
    assert "math" in items[0].tags
    assert "external_live" in items[0].tags

    manifest = adapter.pull_manifest
    assert len(manifest) == 1
    pull = manifest[0]
    assert pull["dataset_id"] == "org/tiny_truth"
    assert pull["subset"] == "default"
    assert pull["split"] == "test"
    assert pull["row_count"] == 2
    assert pull["cache_mode"] == "prefer_cache"
    assert len(pull["content_hash"]) == 64
    assert "fetch_timestamp" in pull
    assert Path(pull["cache_data_path"]).exists()
    assert Path(pull["cache_meta_path"]).exists()

    meta = json.loads(Path(pull["cache_meta_path"]).read_text(encoding="utf-8"))
    assert meta["dataset_id"] == "org/tiny_truth"
    assert meta["subset"] == "default"
    assert meta["split"] == "test"
    assert meta["row_count"] == 2
    assert len(meta["content_hash"]) == 64
    assert "fetch_timestamp" in meta


def test_hf_adapter_schema_validation_and_cache_controls():
    cache_dir = Path("logs/test_tmp_hf_cache_controls")
    _clean_dir(cache_dir)

    spec_bad = DatasetSpec(
        name="BadMap",
        source="external",
        split="test",
        hf_dataset_id="org/bad_map",
        column_mapping={"prompt": "missing_prompt_col"},
    )
    bad_adapter = HFDatasetAdapter(dataset_specs={("truth_core", "BadMap"): spec_bad}, cache_dir=str(cache_dir))
    bad_adapter._load_hf_split = lambda _spec: ("test", [{"id": "x1", "question": "hello"}])  # type: ignore[method-assign]
    try:
        bad_adapter.load("truth_core", "BadMap")
        raise AssertionError("Expected mapping schema validation to fail")
    except ValueError as exc:
        assert "Column mapping validation failed" in str(exc)

    spec_cache = DatasetSpec(
        name="CacheOnly",
        source="external",
        split="test",
        hf_dataset_id="org/cache_only",
        column_mapping={"prompt": "question", "id": "qid"},
    )
    cache_only_adapter = HFDatasetAdapter(
        dataset_specs={("truth_core", "CacheOnly"): spec_cache},
        cache_dir=str(cache_dir),
        cache_only=True,
    )
    try:
        cache_only_adapter.load("truth_core", "CacheOnly")
        raise AssertionError("Expected cache-only miss to fail")
    except RuntimeError as exc:
        assert "Cache-only mode enabled" in str(exc)


def test_hf_adapter_force_refresh_overwrites_cache():
    cache_dir = Path("logs/test_tmp_hf_cache_refresh")
    _clean_dir(cache_dir)

    spec = DatasetSpec(
        name="Refreshable",
        source="external",
        split="test",
        hf_dataset_id="org/refreshable",
        column_mapping={"prompt": "question", "id": "qid"},
    )

    adapter_initial = HFDatasetAdapter(dataset_specs={("truth_core", "Refreshable"): spec}, cache_dir=str(cache_dir))
    adapter_initial._load_hf_split = lambda _spec: ("test", [{"qid": "q1", "question": "old"}])  # type: ignore[method-assign]
    items_initial, _ = adapter_initial.load("truth_core", "Refreshable")
    assert items_initial[0].item_id == "q1"

    adapter_refresh = HFDatasetAdapter(
        dataset_specs={("truth_core", "Refreshable"): spec},
        cache_dir=str(cache_dir),
        force_refresh=True,
    )
    adapter_refresh._load_hf_split = lambda _spec: ("test", [{"qid": "q2", "question": "new"}])  # type: ignore[method-assign]
    items_refresh, _ = adapter_refresh.load("truth_core", "Refreshable")
    assert items_refresh[0].item_id == "q2"
    assert adapter_refresh.pull_manifest[0]["cache_mode"] == "refresh"


if __name__ == "__main__":
    test_hf_adapter_mapping_sampling_hash_and_provenance()
    test_hf_adapter_schema_validation_and_cache_controls()
    test_hf_adapter_force_refresh_overwrites_cache()
    print("test_benchmark_datasets: PASS")
