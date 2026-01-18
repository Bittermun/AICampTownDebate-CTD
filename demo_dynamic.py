"""
Demo: Run a dynamic debate (AI-driven duration) with Ollama backend.
Usage:
  python demo_dynamic.py              # Uses default model
  python demo_dynamic.py qwen2.5:3b   # Specify model
"""
import sys
from src.models import Debater, DebaterConfig, Judge, JudgeConfig
from src.models.ollama_backend import get_backend, OllamaConfig
from src.arena import DynamicDebateRound, TournamentConfig
from src.economy import TokenLedger, BettingManager, TokenDistributor
from src.logs import create_transcript


def main():
    # Determine model from args or use default
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:1.5b"
    
    print("=" * 60)
    print("DYNAMIC DEBATE EXPERIMENT - AI-DRIVEN DURATION")
    print("=" * 60)
    
    # Check Ollama availability
    backend = get_backend(OllamaConfig(model=model))
    if not backend.is_available():
        print("\n❌ Ollama is not running!")
        print("   Start it with: ollama serve")
        print("   Then pull a model: ollama pull qwen2.5:1.5b")
        return
    
    print(f"\nOllama available. Using model: {model}")
    
    # Topic for debate
    topic = "Should AI development be regulated by governments?"
    print(f"\nTopic: {topic}")
    print(f"Mode: Dynamic (continues until both debaters PASS)")
    print(f"Max iterations: 10")
    
    # Config
    config = TournamentConfig(
        initial_balance=200.0,
        max_debt=50.0,
        tokens_per_round=20.0,
    )
    
    # Initialize economy
    ledger = TokenLedger(config.initial_balance, config.max_debt)
    betting = BettingManager(config.betting_fee, config.min_bet)
    distributor = TokenDistributor(config.tokens_per_round)
    
    # Create debaters
    debater_a = Debater(DebaterConfig(
        model_path=f"ollama:{model}",
        name="Debater_Alpha",
        system_prompt="You are a skilled debater who argues FOR the proposition. Be concise.",
    ))
    debater_b = Debater(DebaterConfig(
        model_path=f"ollama:{model}",
        name="Debater_Beta",
        system_prompt="You are a skilled debater who argues AGAINST the proposition. Be concise.",
    ))
    
    # Create judge
    judge = Judge(JudgeConfig(
        model_path=f"ollama:{model}",
        name="Judge_Main",
    ))
    
    # Register debaters
    ledger.register(debater_a.name)
    ledger.register(debater_b.name)
    
    # Load models
    debater_a.load_model()
    debater_b.load_model()
    judge.load_model()
    
    # Create transcript
    transcript = create_transcript({
        "mode": "dynamic",
        "initial_balance": config.initial_balance,
        "max_debt": config.max_debt,
        "max_iterations": 10,
        "debater_a": debater_a.name,
        "debater_b": debater_b.name,
        "judge": judge.name,
    })
    round_transcript = transcript.new_round(1, topic)
    
    try:
        # Create dynamic round
        dynamic_round = DynamicDebateRound(
            debater_a=debater_a,
            debater_b=debater_b,
            judge=judge,
            ledger=ledger,
            betting=betting,
            distributor=distributor,
            max_iterations=10,
        )
        
        print("\n--- Debate Starting ---")
        result = dynamic_round.run(topic, round_id=1, transcript=round_transcript)
        
        print("\n" + "=" * 60)
        print("DYNAMIC DEBATE COMPLETE")
        print("=" * 60)
        print(f"Iterations: {result.iterations_completed}")
        print(f"Termination: {result.termination_reason}")
        print(f"Final Confidence: A={result.final_judgment.confidence_a:.2f}, B={result.final_judgment.confidence_b:.2f}")
        print(f"Tokens Awarded: A={result.tokens_awarded_a:.1f}, B={result.tokens_awarded_b:.1f}")
        print(f"Total Bets Placed: {len(result.all_bets)}")
        print(f"Final Balances:")
        print(f"  {debater_a.name}: {ledger.balance(debater_a.name):.1f} tokens")
        print(f"  {debater_b.name}: {ledger.balance(debater_b.name):.1f} tokens")
        
        # Determine winner
        bal_a = ledger.balance(debater_a.name)
        bal_b = ledger.balance(debater_b.name)
        if bal_a > bal_b:
            winner = debater_a.name
        elif bal_b > bal_a:
            winner = debater_b.name
        else:
            winner = None
        
        print(f"\nWinner: {winner or 'TIE'}")
        
        # Finalize and save transcript
        transcript.finalize(winner, {
            debater_a.name: bal_a,
            debater_b.name: bal_b,
        })
        transcript.save("logs/dynamic_results_transcript.json")
        transcript.save_markdown("logs/dynamic_results_transcript.md")
        print("\nTranscript saved to logs/dynamic_results_transcript.md")
        
    finally:
        debater_a.unload_model()
        debater_b.unload_model()
        judge.unload_model()


if __name__ == "__main__":
    main()
