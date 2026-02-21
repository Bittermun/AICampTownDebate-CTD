#!/usr/bin/env python3
"""
Stress Test: Judge Discrimination
Validates that if one debater provides a strong argument and the other provides gibberish,
the judge correctly identifies the superior argument with high confidence.
"""
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.judge import JudgeConfig, LLMJudge

def run_test():
    print("=== STRESS TEST: Judge Discrimination ===")
    
    config = JudgeConfig(
        model_path="ollama:qwen2.5:1.5b",
        name="DiscriminationTestJudge"
    )
    judge = LLMJudge(config)
    judge.load_model()
    
    topic = "Should governments implement universal basic income (UBI)?"
    
    strong_argument = (
        "Universal Basic Income is a necessary safety net against job displacement from automation. "
        "It provides individuals with financial stability, encouraging them to pursue education, "
        "start businesses, and engage in meaningful work without the constant threat of poverty."
    )
    
    gibberish_argument = (
        "Balloons are mostly blue when the Tuesday is loud. Therefore, bananas are good for the economy "
        "because shoe strings tie themselves. 42 is the answer to UBI if you ask a dolphin."
    )
    
    print(f"Topic: {topic}")
    print(f"Argument A (Strong): {strong_argument}")
    print(f"Argument B (Gibberish): {gibberish_argument}")
    print("\nRunning evaluation (this may take a moment)...")
    
    try:
        judgment = judge.evaluate(
            topic=topic,
            argument_a=strong_argument,
            argument_b=gibberish_argument,
            round_id=1
        )
        
        print("\n=== RESULTS ===")
        print(f"Confidence A (Strong): {judgment.confidence_a:.2f}")
        print(f"Confidence B (Gibberish): {judgment.confidence_b:.2f}")
        
        # We expect a clear win for A
        if judgment.confidence_a > 0.65 and judgment.confidence_b < 0.35:
            print("\n✅ PASS: Judge correctly discriminated the strong argument from gibberish.")
            return True
        else:
            print("\n❌ FAIL: Judge failed to properly discriminate. Confidence gap is too narrow.")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return False

if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
