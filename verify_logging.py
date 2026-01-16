"""
Verification script for payout logging.
Uses stub mode to avoid LLM costs/latency.
"""
from src.models import Debater, DebaterConfig, Judge, JudgeConfig
from src.arena import Tournament, TournamentConfig
import os

def main():
    print("Verifying Payout Logging...")
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Topics
    topics = ["Verification Topic 1", "Verification Topic 2"]
    
    # Stub debaters
    debater_a = Debater(DebaterConfig(model_path="stub", name="Alpha"))
    debater_b = Debater(DebaterConfig(model_path="stub", name="Beta"))
    
    # Stub judge
    judge = Judge(JudgeConfig(model_path="stub", name="Judge"))
    
    # Config
    config = TournamentConfig(
        num_rounds=2,
        initial_balance=100.0,
    )
    
    # Tournament
    tournament = Tournament(
        debater_a=debater_a,
        debater_b=debater_b,
        judge=judge,
        topics=topics,
        config=config,
    )
    
    # Run
    tournament.run()
    
    # Save (this generates the markdown)
    transcript_path = "logs/verify_payouts_transcript"
    tournament.save_results("logs/verify_payouts.json")
    
    print(f"\nVerification complete. Check {transcript_path}.md for 'Bet Resolution' section.")

if __name__ == "__main__":
    main()
