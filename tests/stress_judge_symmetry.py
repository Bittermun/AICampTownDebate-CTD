#!/usr/bin/env python3
"""
Stress Test: Judge Symmetry
Validates that if two debaters provide identical arguments, the judge scores them equally (~50/50).
Checks for positional bias (e.g., always favoring Argument A).
"""
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.judge import JudgeConfig, LLMJudge

def run_test():
    print("=== STRESS TEST: Judge Symmetry ===")
    
    # Initialize judge using the default model
    config = JudgeConfig(
        model_path="ollama:qwen2.5:1.5b",
        name="SymmetryTestJudge"
    )
    judge = LLMJudge(config)
    judge.load_model()
    
    topic = "Should humans colonize Mars?"
    identical_argument = "Colonizing Mars is essential for the long-term survival of humanity. It provides a backup for Earth in case of global catastrophes and drives technological innovation."
    
    print(f"Topic: {topic}")
    print(f"Argument A: {identical_argument}")
    print(f"Argument B: {identical_argument}")
    print("\nRunning evaluation (this may take a moment)...")
    
    try:
        judgment = judge.evaluate(
            topic=topic,
            argument_a=identical_argument,
            argument_b=identical_argument,
            round_id=1
        )
        
        diff = abs(judgment.confidence_a - judgment.confidence_b)
        
        print("\n=== RESULTS ===")
        print(f"Confidence A: {judgment.confidence_a:.2f}")
        print(f"Confidence B: {judgment.confidence_b:.2f}")
        print(f"Difference:   {diff:.2f}")
        
        if diff <= 0.15:
            print("\n✅ PASS: Judge shows acceptable symmetry (diff <= 0.15).")
            return True
        else:
            print(f"\n❌ FAIL: Judge shows positional bias (diff > 0.15).")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return False

if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
