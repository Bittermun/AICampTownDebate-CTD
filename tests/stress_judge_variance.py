#!/usr/bin/env python3
"""
Stress Test: Judge Variance
Validates that if the same argument pair is given to the judge multiple times,
the scoring variance (standard deviation) remains under 5%.
Also acts as a test for the 'Development' dimension penalizing obstinacy.
"""
import sys
import statistics
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.judge import JudgeConfig, LLMJudge

def run_test():
    print("=== STRESS TEST: Judge Variance ===")
    
    # Initialize judge using the default model
    config = JudgeConfig(
        model_path="ollama:qwen2.5:1.5b",
        name="VarianceTestJudge"
    )
    judge = LLMJudge(config)
    judge.load_model()
    
    topic = "Should humans colonize Mars?"
    
    # Simulate a Round 2 scenario where A synthesized B's point, but B is obstinate
    argument_a = "While my opponent correctly points out the immense radiation risks of Mars, this actually strengthens the need to begin now. We must solve these shielding challenges to become a multi-planetary species."
    argument_b = "Colonizing Mars is too expensive. We should spend the money on Earth. Mars is a barren wasteland and we have no business being there."
    
    print(f"Topic: {topic}")
    print("Argument A (Synthesis): Acknowledges opponent's risk point but integrates it into a pro-colonization stance.")
    print("Argument B (Obstinate): Ignores A's points, repeats opening statement.")
    
    iterations = 10
    print(f"\nRunning {iterations} evaluations (this will take a while)...")
    
    confidences_a = []
    
    try:
        for i in range(iterations):
            sys.stdout.write(f"  Run {i+1}/{iterations}... ")
            sys.stdout.flush()
            
            judgment = judge.evaluate(
                topic=topic,
                argument_a=argument_a,
                argument_b=argument_b,
                round_id=2
            )
            
            # The judge's final output normalizes A + B = 1.0. 
            # We track A's confidence to measure variance.
            confidences_a.append(judgment.confidence_a)
            print(f"A={judgment.confidence_a:.3f}, B={judgment.confidence_b:.3f}")
            
        
        # Calculate statistics
        mean_a = statistics.mean(confidences_a)
        stdev_a = statistics.stdev(confidences_a) if len(confidences_a) > 1 else 0.0
        
        print("\n=== RESULTS ===")
        print(f"Mean Confidence A: {mean_a:.3f}")
        print(f"StdDev Confidence A: {stdev_a:.3f} ({(stdev_a*100):.1f}%)")
        print("\nConfidences observed:")
        print([round(c, 3) for c in confidences_a])
        
        # We expect a Low Standard Deviation (<0.05)
        variance_pass = stdev_a <= 0.05
        
        # We also expect Argument A (synthesis) to win over Argument B (obstinacy) on average
        synthesis_pass = mean_a > 0.55
        
        if variance_pass:
            print("\n✅ PASS: Judge shows acceptable variance (StdDev <= 0.05).")
        else:
            print(f"\n❌ FAIL: Judge shows high variance (StdDev > 0.05).")
            
        if synthesis_pass:
            print("✅ PASS: Judge correctly rewarded synthesis / penalized obstinacy (Mean A > 0.55).")
        else:
            print("❌ FAIL: Judge failed to adequately reward synthesis over obstinacy.")
            
        return variance_pass and synthesis_pass
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return False

if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
