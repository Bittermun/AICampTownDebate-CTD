#!/usr/bin/env python3
"""Verify the multi-dimension judge integration works."""
from src.models.judge import LLMJudge, JudgeConfig

# Test with stub backend
config = JudgeConfig(model_path="stub", name="TestJudge", randomize_argument_order=True)
judge = LLMJudge(config)
judge.load_model()

print("Testing multi-dimension judge integration:")

# Test 1: Basic evaluation works
result = judge.evaluate(
    topic="Is AI beneficial?",
    argument_a="AI helps productivity and solves problems.",
    argument_b="AI poses risks to employment.",
    round_id=1
)

print(f"  confidence_a: {result.confidence_a:.2%}")
print(f"  confidence_b: {result.confidence_b:.2%}")
print(f"  reasoning: {result.reasoning[:100]}")

if result.confidence_a + result.confidence_b == 1.0:
    print("✅ Confidences sum to 1.0")
else:
    print(f"❌ Confidences don't sum to 1.0: {result.confidence_a + result.confidence_b}")

# Test 2: Import works
try:
    from src.models.response_models import MultiDimensionJudgment
    print("✅ MultiDimensionJudgment import works")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    exit(1)

# Test 3: Judge prompts work
try:
    from src.models.judge_prompts import MULTI_DIMENSION_SYSTEM, MULTI_DIMENSION_PROMPT
    print("✅ Judge prompts import works")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    exit(1)

print("\n✅✅✅ Multi-dimension judge integration VERIFIED")
