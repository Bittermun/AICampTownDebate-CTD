#!/usr/bin/env python3
"""Unit tests for trace contract normalization/export."""
from pathlib import Path
import json
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.analysis.trace_contract import (  # noqa: E402
    assign_trace_quality_tier,
    export_trace_jsonl,
    normalize_transcript_to_traces,
)


def _sample_transcript() -> dict:
    return {
        "tournament_id": "run_abc",
        "config": {"judge": "Judge_Main"},
        "rounds": [
            {
                "round_id": 1,
                "confidence_a": 0.62,
                "confidence_b": 0.38,
                "tokens_awarded_a": 12.5,
                "tokens_awarded_b": 3.0,
                "turns": [
                    {"speaker": "Debater_A", "type": "argument", "content": "A arg"},
                    {"speaker": "Debater_B", "type": "argument", "content": "B arg"},
                    {
                        "speaker": "Debater_A",
                        "type": "deliberation",
                        "tokens_bet": 5.0,
                        "content": (
                            "**Balance**: 120 tokens | **Standing**: 62% vs 38%\n\n"
                            "**Decision**: RESPOND (bet: 5.0 tokens) | **Intent**: challenge\n"
                            "**Reasoning**: [Iter 2] Attack weak premise"
                        ),
                    },
                    {
                        "speaker": "Debater_B",
                        "type": "deliberation",
                        "tokens_bet": 0.0,
                        "content": (
                            "**Balance**: 80 tokens | **Standing**: 38% vs 62%\n\n"
                            "**Decision**: HOLD (bet: 0.0 tokens) | **Intent**: revise\n"
                            "**Reasoning**: [Iter 2] Wait and conserve budget"
                        ),
                    },
                ],
            }
        ],
    }


def test_normalize_transcript_to_traces_basic() -> None:
    traces = normalize_transcript_to_traces(
        _sample_transcript(),
        run_id="run_abc",
        seed=101,
        judge_model="openai:qwen2.5:7b",
        judge_reliability_tier="tier_a",
    )
    assert len(traces) == 2
    first = traces[0]
    second = traces[1]
    assert first.decision == "RESPOND"
    assert first.intent == "challenge"
    assert first.iteration == 2
    assert round(first.confidence_self or 0.0, 2) == 0.62
    assert first.judge_reliability_tier == "tier_a"
    assert second.decision == "HOLD"
    assert second.outcome_delta == 3.0


def test_export_trace_jsonl_roundtrip() -> None:
    traces = normalize_transcript_to_traces(_sample_transcript(), run_id="run_abc")
    out_path = Path("logs/test_tmp_trace_contract/trace_records.jsonl")
    export_trace_jsonl(traces, str(out_path))
    lines = [ln for ln in out_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == len(traces)
    loaded = [json.loads(ln) for ln in lines]
    assert loaded[0]["trace_id"].startswith("run_abc:r1")


def test_assign_trace_quality_tier() -> None:
    tier_a = assign_trace_quality_tier(
        run_metadata={"runtime_fingerprint": {"strict_runtime": True}},
        gate_summary={"judge_variance_pass": True, "judge_calibration_pass": True},
    )
    tier_b = assign_trace_quality_tier(
        run_metadata={"runtime_fingerprint": {"strict_runtime": True}},
        gate_summary={"judge_variance_pass": True, "judge_calibration_pass": None, "gates_pass": True},
    )
    tier_c = assign_trace_quality_tier(
        run_metadata={"runtime_fingerprint": {"strict_runtime": False}},
        gate_summary={"judge_variance_pass": False, "judge_calibration_pass": False, "gates_pass": False},
    )
    assert tier_a == "tier_a"
    assert tier_b == "tier_b"
    assert tier_c == "tier_c"


if __name__ == "__main__":
    test_normalize_transcript_to_traces_basic()
    test_export_trace_jsonl_roundtrip()
    test_assign_trace_quality_tier()
    print("test_trace_contract: PASS")
