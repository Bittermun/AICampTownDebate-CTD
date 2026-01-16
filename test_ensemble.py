"""
Verification script for Modular Judge Ensemble.
"""
from src.models import JudgeFactory, Debater, DebaterConfig
from src.arena import DebateRound
from src.economy import TokenLedger, BettingManager, TokenDistributor
import os

def main():
    print("Verifying Modular Judge Ensemble...")
    
    # 1. Create a Consensus Judge (modular setup)
    # Using 'stub' for all since we just want to verify logic flow
    judge = JudgeFactory.create_consensus(
        sub_model_paths=["stub", "stub"],
        instructor_model_path="stub",
        name="Council_of_Stubs"
    )
    
    # 2. Setup environment
    ledger = TokenLedger(initial_balance=100.0)
    betting = BettingManager()
    distributor = TokenDistributor()
    
    debater_a = Debater(DebaterConfig(model_path="stub", name="Alpha"))
    debater_b = Debater(DebaterConfig(model_path="stub", name="Beta"))
    
    # 3. Register agents
    ledger.register("Alpha")
    ledger.register("Beta")
    
    # 4. Run a single round
    arena_round = DebateRound(
        debater_a=debater_a,
        debater_b=debater_b,
        judge=judge,
        ledger=ledger,
        betting=betting,
        distributor=distributor
    )
    
    topic = "Should modular software design be the standard?"
    print(f"\nRunning round with judge: {judge.name}")
    result = arena_round.run(topic, round_id=1)
    
    print("\n[RESULT]")
    print(f"Initial Judgment: A={result.initial_judgment.confidence_a:.2f}, B={result.initial_judgment.confidence_b:.2f}")
    print(f"Reasoning matches ConsensusJudge format: {result.initial_judgment.judge_id == judge.name}")
    print(f"Combined Reasoning Snippet:\n{result.initial_judgment.reasoning[:100]}...")
    
    print("\nVerification complete!")

if __name__ == "__main__":
    main()
