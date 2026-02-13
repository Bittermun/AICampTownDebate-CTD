#!/usr/bin/env python3
"""Verify Fix 1: Validation failure still costs tokens."""
from src.models.debater import Debater, DebaterConfig, BetType

config = DebaterConfig(model_path="stub:none", name="TestDebater")
debater = Debater(config)

print("Testing validation failure token cost:")

# Simulate validation failure with tokens
response = "This is not valid JSON at all"
simulated_tokens = 50  # LLM would have used tokens to generate this

result = debater._parse_deliberation(response, balance=100.0, llm_tokens_used=simulated_tokens)

if result.bet_type == BetType.PASS:
    print(f"✅ Validation failure defaulted to PASS")
else:
    print(f"❌ Expected PASS, got {result.bet_type}")
    exit(1)

if result.llm_tokens_used == simulated_tokens:
    print(f"✅ Tokens preserved: {result.llm_tokens_used}")
else:
    print(f"❌ Tokens lost: expected {simulated_tokens}, got {result.llm_tokens_used}")
    exit(1)

print("\n✅✅✅ Fix 1 VERIFIED: Validation failures still cost tokens")
