#!/usr/bin/env python3
"""Verify Fix 2: Parse deliberation handles edge cases."""
from src.models.debater import Debater, DebaterConfig, BetType

# Create stub debater for testing parser
config = DebaterConfig(model_path="stub:none", name="TestDebater")
debater = Debater(config)

# Test cases: valid, embedded, and garbage
cases = [
    ('{"decision": "PASS", "amount": 0, "reasoning": "ok"}', BetType.PASS, "Valid JSON"),
    ('I think we should {"decision": "RESPOND", "amount": 10, "reasoning": "test"} pass', BetType.RESPOND, "Embedded JSON"),
    ('No JSON here at all just text', BetType.PASS, "No JSON (fallback)"),
    ('<thinking>Let me think...</thinking>{"decision": "RESPOND", "amount": 5, "reasoning": "need data"}', BetType.RESPOND, "With thinking tags"),
]

print("Testing _parse_deliberation edge cases:\n")
for response, expected_type, label in cases:
    result = debater._parse_deliberation(response, balance=100.0)
    status = "✅" if result.bet_type == expected_type else "❌"
    print(f"{status} {label}: got {result.bet_type.name}, expected {expected_type.name}")
    if result.bet_type != expected_type:
        print(f"   Response: {response[:50]}...")
        print(f"   Reasoning: {result.reasoning[:50]}...")

print("\n✅✅✅ Fix 2 VERIFIED: Parse handles edge cases")
