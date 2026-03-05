#!/usr/bin/env python3
"""Tests for experimental multi-agent injection path in Debater."""
from pathlib import Path
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.debater import Debater, DebaterConfig


def test_auto_injection_enabled_adds_trace_prefix() -> None:
    debater = Debater(
        DebaterConfig(
            model_path="stub",
            name="Alpha",
            strict_runtime=False,
            multi_agent_enabled=True,
            multi_agent_mode="critique",
            multi_agent_min_balance=0.0,
        )
    )
    debater.load_model()
    try:
        arg = debater.generate_argument(
            topic="Should AI labs publish eval artifacts by default?",
            round_id=1,
            opponent_argument="No, transparency creates strategic and legal risk.",
            own_history="Transparency improves accountability.",
            current_balance=120.0,
            confidence_self=0.45,
            confidence_opponent=0.55,
        )
    finally:
        debater.unload_model()

    assert "[INJECTION_CRITIQUE]" in arg.thinking


def test_auto_injection_skips_when_balance_below_threshold() -> None:
    debater = Debater(
        DebaterConfig(
            model_path="stub",
            name="Beta",
            strict_runtime=False,
            multi_agent_enabled=True,
            multi_agent_mode="synthesize",
            multi_agent_min_balance=500.0,
        )
    )
    debater.load_model()
    try:
        arg = debater.generate_argument(
            topic="Do adversarial benchmarks improve deployment readiness?",
            round_id=1,
            opponent_argument="Yes, they reveal hidden failure modes.",
            own_history="Benchmarks can overfit if static.",
            current_balance=120.0,
            confidence_self=0.52,
            confidence_opponent=0.48,
        )
    finally:
        debater.unload_model()

    assert "[INJECTION_SYNTHESIZE]" not in arg.thinking


if __name__ == "__main__":
    test_auto_injection_enabled_adds_trace_prefix()
    test_auto_injection_skips_when_balance_below_threshold()
    print("test_debater_multi_agent: PASS")
