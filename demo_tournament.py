#!/usr/bin/env python3
"""
Demo: Multi-Round Tournament with DynamicDebateRound

Run with:
    python demo_tournament.py --config configs/tournament_config.yaml
"""

import argparse
from pathlib import Path

from src.config_loader import load_config, get_default_config
from src.models import Debater, DebaterConfig
from src.models.judge import LLMJudge, JudgeConfig
from src.arena.tournament import Tournament, EconomyParams
from src.arena.observers import MetricsObserver


def main():
    parser = argparse.ArgumentParser(description="Run a multi-round debate tournament")
    parser.add_argument(
        "--config", 
        type=str, 
        default=None,
        help="Path to tournament config YAML file"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="qwen2.5:1.5b",
        help="Default model if no config file provided"
    )
    args = parser.parse_args()
    
    # Load configuration
    if args.config:
        print(f"Loading config from {args.config}...")
        cfg = load_config(args.config)
    else:
        print(f"Using default config with model: {args.model}")
        cfg = get_default_config()
        for d in cfg.debaters:
            d.model = args.model
        for j in cfg.judges:
            j.model = args.model
    
    # Create debaters using DebaterConfig
    debater_a = Debater(DebaterConfig(
        model_path=f"ollama:{cfg.debaters[0].model}",
        name=f"Debater_{cfg.debaters[0].name}",
        system_prompt=cfg.debaters[0].system_prompt,
    ))
    debater_b = Debater(DebaterConfig(
        model_path=f"ollama:{cfg.debaters[1].model}",
        name=f"Debater_{cfg.debaters[1].name}",
        system_prompt=cfg.debaters[1].system_prompt,
    ))
    
    # Create judge
    judge_config = JudgeConfig(
        model_path=f"ollama:{cfg.judges[0].model}",
        name="Judge_Main",
        randomize_argument_order=cfg.randomize_argument_order,
    )
    judge = LLMJudge(config=judge_config)
    
    # Create observer
    observer = MetricsObserver()
    
    # Build economy params
    economy_params = EconomyParams(
        num_rounds=cfg.rounds.num_rounds,
        initial_balance=cfg.economy.initial_balance,
        max_debt=cfg.economy.max_debt,
        tokens_per_round=cfg.economy.tokens_per_round,
    )
    
    # Create tournament
    tournament = Tournament(
        debater_a=debater_a,
        debater_b=debater_b,
        judge=judge,
        topics=cfg.rounds.topics,
        config=economy_params,
        enable_transcript=True,
        observers=[observer],
        split_pot_enabled=cfg.economy.split_pot_enabled,
        initial_pot_amount=cfg.economy.initial_pot_amount,
    )
    
    print(f"\n{'='*60}")
    print(f"TOURNAMENT: {cfg.debaters[0].name} vs {cfg.debaters[1].name}")
    print(f"Rounds: {cfg.rounds.num_rounds}")
    print(f"Topics: {len(cfg.rounds.topics)}")
    print(f"Split Pot: {cfg.economy.split_pot_enabled}")
    print(f"{'='*60}\n")
    
    # Run tournament
    result = tournament.run()
    
    # Print results
    print(f"\n{'='*60}")
    print("TOURNAMENT RESULTS")
    print(f"{'='*60}")
    print(f"Winner: {result.winner or 'TIE'}")
    if result.eliminated:
        print(f"Eliminated (bankrupt): {result.eliminated}")
    print(f"Final Balances: {result.final_balances}")
    print(f"Rounds Completed: {len(result.rounds)}")
    print(f"Started: {result.started_at}")
    print(f"Ended: {result.ended_at}")
    
    # Save results
    output_dir = Path("logs")
    output_dir.mkdir(exist_ok=True)
    tournament.save_results(str(output_dir / "tournament_results.json"))
    
    # Save observer metrics
    observer.save(str(output_dir / "tournament_metrics.json"))
    
    print(f"\nResults saved to {output_dir}")


if __name__ == "__main__":
    main()
