#!/usr/bin/env python3
"""Tests for batch utility helpers."""
from pathlib import Path
import json
import sys

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark.batch_utils import (
    BatchRunRecord,
    append_jsonl,
    decode_checkpoint_row,
    detect_bankruptcy_from_summary,
    encode_checkpoint_row,
    load_checkpoint_jsonl,
    persist_jsonl,
    should_retry_bankruptcy,
    summarize_batch,
)


def test_detect_bankruptcy_from_summary():
    td = Path("logs/test_tmp_batch_utils")
    td.mkdir(parents=True, exist_ok=True)
    result_path = td / "tournament_results.json"
    result_path.write_text(json.dumps({"final_balances": {"A": 0.0, "B": 120.0}}), encoding="utf-8")
    summary = {
        "seed_results": [
            {
                "artifact_paths": {
                    "results_json": str(result_path),
                }
            }
        ]
    }
    assert detect_bankruptcy_from_summary(summary) is True


def test_retry_policy():
    assert should_retry_bankruptcy(bankrupt=True, attempt=1, max_retries=1) is True
    assert should_retry_bankruptcy(bankrupt=True, attempt=2, max_retries=1) is False
    assert should_retry_bankruptcy(bankrupt=False, attempt=1, max_retries=1) is False


def test_summarize_batch():
    rows = [
        BatchRunRecord(
            run_id="r1",
            attempt=1,
            seed=101,
            topic_set="set01",
            summary_path="a.json",
            registry_path="a-reg.json",
            return_code=0,
            bankrupt=False,
            terminal_bankrupt=False,
            final_pass=True,
            benchmark_score_pass=True,
            gates_pass=True,
            validity_pass=True,
            degraded_mode=False,
            live_source_failures=0,
        ),
        BatchRunRecord(
            run_id="r2",
            attempt=2,
            seed=202,
            topic_set="set01",
            summary_path="b.json",
            registry_path="b-reg.json",
            return_code=2,
            bankrupt=True,
            terminal_bankrupt=True,
            final_pass=False,
            benchmark_score_pass=False,
            gates_pass=False,
            validity_pass=False,
            degraded_mode=True,
            live_source_failures=1,
        ),
    ]
    agg = summarize_batch(rows)
    assert agg["runs"] == 2
    assert agg["final_pass_rate"] == 0.5
    assert agg["bankruptcy_rate"] == 0.5
    assert agg["live_source_failure_runs"] == 1
    assert agg["replacement_run_count"] == 0
    assert agg["replacement_success_rate"] == 0.0


def test_summarize_batch_replacement_metrics():
    rows = [
        BatchRunRecord(
            run_id="r1",
            attempt=2,
            seed=101,
            topic_set="set01",
            summary_path="a.json",
            registry_path="a-reg.json",
            return_code=2,
            bankrupt=True,
            terminal_bankrupt=True,
            final_pass=False,
            original_model_id="ollama:qwen2.5:7b",
            effective_model_id="ollama:qwen2.5:7b",
            was_replaced=False,
            replacement_index=0,
        ),
        BatchRunRecord(
            run_id="r1__replacement1",
            attempt=1,
            seed=101,
            topic_set="set01",
            summary_path="b.json",
            registry_path="b-reg.json",
            return_code=0,
            bankrupt=False,
            terminal_bankrupt=False,
            final_pass=True,
            original_model_id="ollama:qwen2.5:7b",
            effective_model_id="ollama:qwen2.5:14b",
            was_replaced=True,
            replacement_index=1,
            replaced_from_run_id="r1",
        ),
    ]
    agg = summarize_batch(rows)
    assert agg["runs"] == 2
    assert agg["replacement_run_count"] == 1
    assert agg["replacement_success_rate"] == 1.0


def test_batch_record_serializes_openai_endpoint():
    row = BatchRunRecord(
        run_id="r3",
        attempt=1,
        seed=303,
        topic_set="set01",
        summary_path="c.json",
        registry_path="c-reg.json",
        return_code=0,
        bankrupt=False,
        terminal_bankrupt=False,
        openai_base_url="http://arc:8000",
    )
    payload = row.to_dict()
    assert payload["openai_base_url"] == "http://arc:8000"


def test_checkpoint_envelope_decode_supports_legacy_rows() -> None:
    schema = "benchmark.test.batch_summary"
    legacy_row = {"run_no": 1, "success": True}
    wrapped_row = encode_checkpoint_row({"run_no": 2, "success": False}, schema_name=schema)

    legacy_decoded, legacy_version = decode_checkpoint_row(legacy_row, schema_name=schema)
    wrapped_decoded, wrapped_version = decode_checkpoint_row(wrapped_row, schema_name=schema)

    assert legacy_decoded == legacy_row
    assert legacy_version == 0
    assert wrapped_decoded == {"run_no": 2, "success": False}
    assert wrapped_version == 1


def test_load_checkpoint_jsonl_migrates_legacy_and_skips_invalid(tmp_path: Path) -> None:
    schema = "benchmark.test.batch_summary"
    path = tmp_path / "batch_summary.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"run_no": 1, "success": True}),
                json.dumps(encode_checkpoint_row({"run_no": 2, "success": False}, schema_name=schema)),
                "{broken json",
                json.dumps({"__schema__": schema, "__version__": 999, "record": {"run_no": 3}}),
            ]
        ),
        encoding="utf-8",
    )

    rows, stats = load_checkpoint_jsonl(str(path), schema_name=schema)
    assert rows == [{"run_no": 1, "success": True}, {"run_no": 2, "success": False}]
    assert stats["rows_legacy"] == 1
    assert stats["rows_enveloped"] == 1
    assert stats["rows_malformed"] == 1
    assert stats["rows_invalid"] == 1


def test_persist_jsonl_uses_atomic_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schema = "benchmark.test.batch_summary"
    path = tmp_path / "batch_summary.jsonl"
    path.write_text("stale\n", encoding="utf-8")

    calls: list[tuple[Path, Path]] = []
    original_replace = Path.replace

    def _spy_replace(self: Path, target: Path) -> Path:
        calls.append((self, target))
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", _spy_replace)
    persist_jsonl(str(path), [{"run_no": 1, "success": True}], schema_name=schema)

    assert calls, "persist_jsonl should atomically swap temp -> target via Path.replace"
    rows, stats = load_checkpoint_jsonl(str(path), schema_name=schema)
    assert rows == [{"run_no": 1, "success": True}]
    assert stats["rows_invalid"] == 0
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]


def test_append_jsonl_writes_enveloped_rows(tmp_path: Path) -> None:
    schema = "benchmark.test.batch_summary"
    path = tmp_path / "batch_summary.jsonl"
    append_jsonl(str(path), {"run_no": 1, "success": True}, schema_name=schema)
    append_jsonl(str(path), {"run_no": 2, "success": False}, schema_name=schema)

    rows, stats = load_checkpoint_jsonl(str(path), schema_name=schema)
    assert rows == [{"run_no": 1, "success": True}, {"run_no": 2, "success": False}]
    assert stats["rows_enveloped"] == 2


if __name__ == "__main__":
    test_detect_bankruptcy_from_summary()
    test_retry_policy()
    test_summarize_batch()
    test_summarize_batch_replacement_metrics()
    test_batch_record_serializes_openai_endpoint()
    test_checkpoint_envelope_decode_supports_legacy_rows()
    print("test_benchmark_batch_utils: PASS")
