"""
Demo: Run a simple stub tournament to test the framework.
No actual LLM calls - uses stub responses.
"""
from src.models import Debater, DebaterConfig, Judge, JudgeConfig
from src.arena import Tournament, TournamentConfig


def main():
    # Sample topics
    topics = [
        "Is renewable energy more important than nuclear energy for addressing climate change?",
        "Should AI development be regulated by governments?",
        "Is remote work better for productivity than office work?",
        "Should social media companies be responsible for user content?",
        "Is universal basic income a viable economic policy?",
    ]
    
    # Create debaters (stub mode - no real models)
    debater_a = Debater(DebaterConfig(
        model_path="stub",
        name="Debater_Alpha",
    ))
    debater_b = Debater(DebaterConfig(
        model_path="stub",
        name="Debater_Beta",
    ))
    
    # Create judge
    judge = Judge(JudgeConfig(
        model_path="stub",
        name="Judge_Main",
    ))
    
    # Tournament config
    config = TournamentConfig(
        num_rounds=5,
        initial_balance=100.0,
        max_debt=50.0,
        tokens_per_round=20.0,
        betting_fee=0.05,
        min_bet=5.0,
    )
    
    # Run tournament
    print("=" * 60)
    print("TOKEN-DEBATE EXPERIMENT - STUB DEMO")
    print("=" * 60)
    
    tournament = Tournament(
        debater_a=debater_a,
        debater_b=debater_b,
        judge=judge,
        topics=topics,
        config=config,
    )
    
    result = tournament.run()
    
    # Summary
    print("\n" + "=" * 60)
    print("TOURNAMENT COMPLETE")
    print("=" * 60)
    print(f"Rounds: {config.num_rounds}")
    print(f"Winner: {result.winner or 'TIE'}")
    print(f"Final Balances:")
    for name, balance in result.final_balances.items():
        print(f"  {name}: {balance:.1f} tokens")
    
    # Save results
    tournament.save_results("logs/demo_results.json")
    print("\nResults saved to logs/demo_results.json")


if __name__ == "__main__":
    main()
