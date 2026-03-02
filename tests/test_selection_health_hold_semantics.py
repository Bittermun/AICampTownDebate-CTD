#!/usr/bin/env python3
"""Regression tests for HOLD/PASS semantics in selection health metrics."""
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.analysis import compute_selection_health


def test_hold_counts_as_pass_for_rates_and_mutual_pass() -> None:
    transcript = {
        "config": {"debater_a": "A", "debater_b": "B"},
        "final_balances": {"A": 100.0, "B": 100.0},
        "rounds": [
            {
                "round_id": 1,
                "turns": [
                    {"speaker": "A", "type": "deliberation", "content": "**Decision**: HOLD (bet: 0.0 tokens)"},
                    {"speaker": "B", "type": "deliberation", "content": "**Decision**: PASS (bet: 0.0 tokens)"},
                    {"speaker": "Judge", "type": "judgment", "confidence_a": 0.5, "confidence_b": 0.5},
                ],
            }
        ],
    }

    report = compute_selection_health(transcript=transcript, results=None, ledger=None)
    assert report.pass_rate == 1.0
    assert report.aggression_rate == 0.0
    assert report.mutual_pass_round_rate == 1.0


if __name__ == "__main__":
    test_hold_counts_as_pass_for_rates_and_mutual_pass()
    print("test_selection_health_hold_semantics: PASS")
