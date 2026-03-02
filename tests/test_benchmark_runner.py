import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark.runner import _extract_round_decisions


def test_extract_round_decisions_treats_hold_as_pass() -> None:
    transcript = {
        "rounds": [
            {
                "turns": [
                    {"type": "deliberation", "content": "**Decision**: HOLD (bet: 0.0 tokens)"},
                    {"type": "deliberation", "content": "**Decision**: RESPOND (bet: 10.0 tokens)"},
                ]
            },
            {
                "turns": [
                    {"type": "deliberation", "content": "**Decision**: PASS (bet: 0.0 tokens)"},
                    {"type": "deliberation", "content": "**Decision**: HOLD (bet: 0.0 tokens)"},
                    {"type": "deliberation", "content": "**Decision**: RESPOND (bet: 8.0 tokens)"},
                ]
            },
        ]
    }

    decisions = _extract_round_decisions(transcript)
    assert decisions == [(1, 1), (2, 1)]


if __name__ == "__main__":
    test_extract_round_decisions_treats_hold_as_pass()
    print("test_benchmark_runner: PASS")
