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

    adapter._load_hf_split = lambda _spec: (_ for _ in ()).throw(AssertionError("should read from cache"))  # type: ignore[method-assign]
    items_cached, degraded_cached = adapter.load(group_name="truth_core", dataset_name="TinyTruth", limit=None)
    assert degraded_cached is False
    assert len(items_cached) == 2
    assert items_cached[1].item_id == "q2"


if __name__ == "__main__":
    test_hf_adapter_mapping_sampling_hash_and_provenance()
    print("test_benchmark_datasets: PASS")
