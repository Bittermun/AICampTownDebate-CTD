"""
Arena CLI: Unified entry point for running debates and tournaments.
Usage:
  python arena_cli.py --model ollama:qwen2.5:1.5b --rounds 3
  python arena_cli.py --judge-mode consensus --model ollama:llama3:8b
"""
import argparse
import sys
from src.models import Debater, DebaterConfig, JudgeFactory, JudgeConfig
from src.arena import Tournament, TournamentConfig
from src.models.ollama_backend import get_backend, OllamaConfig

def main():
    parser = argparse.ArgumentParser(description="Unified Token-Debate Arena CLI")
    parser.add_argument("--model", type=str, default="ollama:qwen2.5:1.5b", help="Model path (e.g. ollama:llama3, stub)")
    parser.add_argument("--rounds", type=int, default=3, help="Number of rounds")
    parser.add_argument("--balance", type=float, default=200.0, help="Initial token balance")
    parser.add_argument("--judge-mode", choices=["single", "ensemble", "consensus"], default="single", help="Judging mode")
    parser.add_argument("--instructor", type=str, help="Instructor model for consensus mode")
    parser.add_argument("--output", type=str, default="logs/last_run.json", help="Output path for results")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("TOKEN-DEBATE EXPERIMENT - UNIFIED ARENA")
    print("=" * 60)
    
    # Setup Judge
    if args.judge_mode == "single":
        judge = JudgeFactory.create_simple(args.model, name="Judge_Main")
    elif args.judge_mode == "ensemble":
        # Example ensemble: 3 instances of the same model (or mix)
        judge = JudgeFactory.create_ensemble([args.model, args.model, args.model], name="Council_of_Three")
    else: # consensus
        instructor_model = args.instructor or args.model
        judge = JudgeFactory.create_consensus(
            [args.model, args.model], 
            instructor_model,
            name="Supreme_Consensus"
        )
    
    # Setup Debaters
    debater_a = Debater(DebaterConfig(
        model_path=args.model,
        name="Debater_Alpha",
        system_prompt="You are a skilled debater who argues FOR the proposition. Be concise and strategic.",
    ))
    debater_b = Debater(DebaterConfig(
        model_path=args.model,
        name="Debater_Beta",
        system_prompt="You are a skilled debater who argues AGAINST the proposition. Be concise and strategic.",
    ))
    
    # Configuration
    config = TournamentConfig(
        num_rounds=args.rounds,
        initial_balance=args.balance,
        max_debt=50.0,
    )
    
    topics = [
        "Is renewable energy more important than nuclear energy for climate change?",
        "Should AI development be regulated by governments?",
        "Is remote work better for productivity than office work?",
    ]
    if args.rounds > len(topics):
        # Repeat or fill
        topics = (topics * (args.rounds // len(topics) + 1))[:args.rounds]
    else:
        topics = topics[:args.rounds]
    
    # Run
    tournament = Tournament(
        debater_a=debater_a,
        debater_b=debater_b,
        judge=judge,
        topics=topics,
        config=config,
    )
    
    result = tournament.run()
    
    print("\n" + "=" * 60)
    print("TOURNAMENT COMPLETE")
    print(f"Winner: {result.winner or 'TIE'}")
    print("=" * 60)
    
    tournament.save_results(args.output)
    print(f"\nResults saved to {args.output}")

if __name__ == "__main__":
    main()
