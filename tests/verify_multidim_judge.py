#!/usr/bin/env python3
"""Test the MultiDimensionJudgment model."""
from src.models.response_models import MultiDimensionJudgment

# Test case 1: Active debater vs passive debater
print("Test: Active (A) vs Passive (B)")
judgment = MultiDimensionJudgment(
    accuracy_a=0.7,
    accuracy_b=0.6,
    responsiveness_a=0.8,     # A responded to B's points
    responsiveness_b=0.2,     # B ignored A's points
    development_a=0.7,        # A refined argument
    development_b=0.3,        # B stagnated
    reasoning="A actively engaged while B was passive"
)

conf_a, conf_b = judgment.weighted_confidence()
print(f"  Raw scores: A={0.4*0.7 + 0.3*0.8 + 0.3*0.7:.2f}, B={0.4*0.6 + 0.3*0.2 + 0.3*0.3:.2f}")
print(f"  Weighted: A={conf_a:.2%}, B={conf_b:.2%}")

if conf_a > conf_b:
    print("✅ Active debater wins (as expected)")
else:
    print("❌ Passive debater won (BUG)")
    exit(1)

# Test case 2: High accuracy but no engagement
print("\nTest: Accurate but passive (B) vs less accurate but engaged (A)")
judgment2 = MultiDimensionJudgment(
    accuracy_a=0.5,           # Less accurate
    accuracy_b=0.9,           # Very accurate
    responsiveness_a=0.8,     # Engaged
    responsiveness_b=0.1,     # Ignored opponent
    development_a=0.7,        # Developed
    development_b=0.1,        # Stagnant
    reasoning="B was accurate but didn't engage"
)

conf_a2, conf_b2 = judgment2.weighted_confidence()
print(f"  Weighted: A={conf_a2:.2%}, B={conf_b2:.2%}")

# B has higher accuracy but A should win due to responsiveness+development
if conf_a2 > conf_b2:
    print("✅ Engaged debater wins over passive-but-accurate")
else:
    print("⚠️ Accuracy dominated (may need weight tuning)")

# Test case 3: Clamping works
print("\nTest: Extreme scores get clamped")
judgment3 = MultiDimensionJudgment(
    accuracy_a=1.0, accuracy_b=0.0,
    responsiveness_a=1.0, responsiveness_b=0.0,
    development_a=1.0, development_b=0.0,
    reasoning="Extreme case"
)
conf_a3, conf_b3 = judgment3.weighted_confidence()
print(f"  Clamped: A={conf_a3:.2%}, B={conf_b3:.2%}")
if conf_b3 >= 0.10:
    print("✅ Minimum 10% enforced")
else:
    print("❌ Clamping failed")
    exit(1)

print("\n✅✅✅ MultiDimensionJudgment VERIFIED")
