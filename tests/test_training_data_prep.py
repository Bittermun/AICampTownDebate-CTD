#!/usr/bin/env python3
"""Tests dataset preparation from benchmark summary + trace artifacts."""
from pathlib import Path
import json
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.training.data_prep import build_training_data_from_summary  # noqa: E402


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    payload = "\n".join(json.dumps(r) for r in rows) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _make_summary(tmp: Path) -> Path:
    trace_a = tmp / "seed_101_trace.jsonl"
    trace_b = tmp / "seed_202_trace.jsonl"
    _write_jsonl(
        trace_a,
        [
            {
                "trace_id": "a1",
                "round_id": 1,
                "iteration": 1,
                "speaker": "Debater_A",
                "decision": "RESPOND",
                "reasoning": "attack",
                "intent": "challenge",
                "outcome_delta": 10.0,
                "judge_reliability_tier": "tier_a",
                "provenance_source": "raw_transcript",
            }
        ],
    )
    _write_jsonl(
        trace_b,
        [
            {
                "trace_id": "b1",
                "round_id": 1,
                "iteration": 1,
                "speaker": "Debater_B",
                "decision": "HOLD",
                "reasoning": "wait",
                "intent": "revise",
                "outcome_delta": 1.0,
                "judge_reliability_tier": "tier_c",
                "provenance_source": "raw_transcript",
            }
        ],
    )
    summary = {
        "run_metadata": {"run_id": "run_smoke_1"},
        "seed_results": [
            {"seed": 101, "artifact_paths": {"trace_jsonl": str(trace_a)}},
            {"seed": 202, "artifact_paths": {"trace_jsonl": str(trace_b)}},
        ],
    }
    summary_path = tmp / "benchmark_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary_path


def test_build_training_data_from_summary_filters_by_tier() -> None:
    base = Path("logs/test_tmp_training_data_prep")
    summary_path = _make_summary(base / "input")
    out = base / "out"

    result = build_training_data_from_summary(
        str(summary_path),
        output_dir=str(out),
        min_tier="tier_b",
    )
    assert result.trace_count_input == 2
    assert result.trace_count_selected == 1
    assert result.sft_count == 1
    assert result.preference_count == 0
    assert Path(result.sft_path).exists()
    assert Path(result.preference_path).exists()
    assert Path(result.manifest_path).exists()


def test_build_training_data_from_summary_rejects_empty_selection() -> None:
    base = Path("logs/test_tmp_training_data_prep_empty")
    summary_path = _make_summary(base / "input")
    try:
        build_training_data_from_summary(
            str(summary_path),
            output_dir=str(base / "out"),
            min_tier="tier_a",
            include_tiers=["tier_c"],
        )
        assert False, "Expected ValueError when no traces match filters"
    except ValueError as exc:
        assert "No traces passed filtering" in str(exc)


if __name__ == "__main__":
    test_build_training_data_from_summary_filters_by_tier()
    test_build_training_data_from_summary_rejects_empty_selection()
    print("test_training_data_prep: PASS")
