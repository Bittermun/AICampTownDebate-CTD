"""
Demo: Run a tournament with Ollama backend.
Usage:
  python demo_ollama.py              # Uses default model
  python demo_ollama.py qwen2.5:3b   # Specify model
"""
import sys
from src.models import Debater, DebaterConfig, Judge, JudgeConfig
from src.models.ollama_backend import get_backend, OllamaConfig
from src.arena import Tournament, TournamentConfig


def main():
    # Determine model from args or use default
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:1.5b"
    
    print("=" * 60)
    print("TOKEN-DEBATE EXPERIMENT - OLLAMA")
    print("=" * 60)
    
    # Check Ollama availability
    backend = get_backend(OllamaConfig(model=model))
    if not backend.is_available():
        print("\n❌ Ollama is not running!")
        print("   Start it with: ollama serve")
        print("   Then pull a model: ollama pull qwen2.5:1.5b")
        return
    
    # Check if model exists
    available = backend.list_models()
    print(f"\nOllama available. Models: {available}")
    
    if model not in available and f"{model}:latest" not in available:
        print(f"\n⚠️  Model '{model}' not found. Pulling...")
        backend.pull_model(model)
    
    # Topics for debate
    topics = [
        "Is renewable energy more important than nuclear energy for climate change?",
        "Should AI development be regulated by governments?",
        "Is remote work better for productivity than office work?",
    ]
    
    # Create debaters with Ollama backend
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
    
    # Tournament config - 20:1 token economy, 200 starting balance
    config = TournamentConfig(
        num_rounds=3,
        initial_balance=200.0,
        max_debt=50.0,
    )
    
    # Run tournament
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
    tournament.save_results("logs/ollama_results.json")
    print("\nResults saved to logs/ollama_results.json")


if __name__ == "__main__":
    main()
