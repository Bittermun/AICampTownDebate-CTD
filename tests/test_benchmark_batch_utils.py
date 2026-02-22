#!/usr/bin/env python3
"""Tests for batch utility helpers."""
from pathlib import Path
import json
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark.batch_utils import BatchRunRecord, detect_bankruptcy_from_summary, should_retry_bankruptcy, summarize_batch


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


if __name__ == "__main__":
    test_detect_bankruptcy_from_summary()
    test_retry_policy()
    test_summarize_batch()
    test_summarize_batch_replacement_metrics()
    print("test_benchmark_batch_utils: PASS")
