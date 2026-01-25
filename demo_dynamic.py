"""
Demo: Run a dynamic debate (AI-driven duration) with Ollama backend.
Usage:
  python demo_dynamic.py                           # Uses defaults
  python demo_dynamic.py --config path/to/config.yaml  # Uses config file
"""
import sys
import argparse
from src.models import Debater, DebaterConfig, Judge, JudgeConfig
from src.models.ollama_backend import get_backend, OllamaConfig
from src.arena import DynamicDebateRound, TournamentConfig
from src.arena.observers import MetricsObserver, save_observations
from src.economy import TokenLedger, BettingManager, TokenDistributor
from src.logs import create_transcript
from src.config_loader import load_config, get_default_config


def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="Run a dynamic debate")
    parser.add_argument("--config", type=str, help="Path to tournament config YAML")
    parser.add_argument("model", nargs="?", default=None, help="Fallback model (legacy)")
    args = parser.parse_args()
    
    # Load configuration
    if args.config:
        print(f"Loading config from: {args.config}")
        tc = load_config(args.config)
    else:
        tc = get_default_config()
        # Override with legacy model arg if provided
        if args.model:
            for d in tc.debaters:
                d.model = args.model
            for j in tc.judges:
                j.model = args.model
    
    print("=" * 60)
    print("DYNAMIC DEBATE EXPERIMENT - AI-DRIVEN DURATION")
    print("=" * 60)
    
    # Check Ollama availability with first debater's model
    test_model = tc.debaters[0].model if tc.debaters else "qwen2.5:1.5b"
    backend = get_backend(OllamaConfig(model=test_model))
    if not backend.is_available():
        print("\n❌ Ollama is not running!")
        print("   Start it with: ollama serve")
        return
    
    print(f"\nOllama available.")
    print(f"Debaters: {', '.join(f'{d.name}@{d.model}' for d in tc.debaters)}")
    print(f"Judge: {tc.judges[0].model if tc.judges else 'default'}")
    
    # Topic for debate
    topic = tc.rounds.topic
    print(f"\nTopic: {topic}")
    print(f"Mode: Dynamic (continues until both debaters PASS)")
    print(f"Max iterations: {tc.rounds.max_iterations}")
    
    # Config - use economy settings from tournament config
    config = TournamentConfig(
        initial_balance=tc.economy.initial_balance,
        max_debt=tc.economy.max_debt,
        tokens_per_round=tc.economy.tokens_per_round,
    )
    
    # Initialize economy
    ledger = TokenLedger(config.initial_balance, config.max_debt)
    betting = BettingManager(config.betting_fee, config.min_bet)
    distributor = TokenDistributor(config.tokens_per_round)
    
    # Create debaters from config
    debater_a = Debater(DebaterConfig(
        model_path=f"ollama:{tc.debaters[0].model}",
        name=f"Debater_{tc.debaters[0].name}",
        system_prompt=tc.debaters[0].system_prompt,
    ))
    debater_b = Debater(DebaterConfig(
        model_path=f"ollama:{tc.debaters[1].model}",
        name=f"Debater_{tc.debaters[1].name}",
        system_prompt=tc.debaters[1].system_prompt,
    ))
    
    # Create judge(s) from config - supports single, ensemble, and consensus
    from src.models.judge import EnsembleJudge, ConsensusJudge, LLMJudge
    
    if tc.judge_type == "consensus" and len(tc.judges) > 1:
        # ConsensusJudge with instructor (lead judge)
        sub_judges = []
        for i, j_spec in enumerate(tc.judges):
            sub_judge = LLMJudge(JudgeConfig(
                model_path=f"ollama:{j_spec.model}",
                name=j_spec.name or f"Judge_{i+1}",
                randomize_argument_order=tc.randomize_argument_order,
            ))
            sub_judges.append(sub_judge)
        
        # Instructor analyzes sub-judge reports and makes final decision
        instructor_model = tc.instructor_model or tc.judges[0].model
        instructor = LLMJudge(JudgeConfig(
            model_path=f"ollama:{instructor_model}",
            name="Lead_Instructor",
            randomize_argument_order=tc.randomize_argument_order,
        ))
        judge = ConsensusJudge(sub_judges, instructor, name="Consensus_Judge")
        print(f"Created consensus with {len(sub_judges)} sub-judges + instructor")
    elif tc.judge_type == "ensemble" or len(tc.judges) > 1:
        # Ensemble of judges (averaging)
        sub_judges = []
        for i, j_spec in enumerate(tc.judges):
            sub_judge = LLMJudge(JudgeConfig(
                model_path=f"ollama:{j_spec.model}",
                name=j_spec.name or f"Judge_{i+1}",
                randomize_argument_order=tc.randomize_argument_order,
            ))
            sub_judges.append(sub_judge)
        judge = EnsembleJudge(sub_judges, name="Ensemble_Judge")
        print(f"Created ensemble with {len(sub_judges)} judges (averaging)")
    else:
        # Single judge
        judge = Judge(JudgeConfig(
            model_path=f"ollama:{tc.judges[0].model}",
            name=tc.judges[0].name or "Judge_Main",
            randomize_argument_order=tc.randomize_argument_order,
        ))
    
    # Create observers
    metrics_observer = MetricsObserver()
    
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
        # Create dynamic round with observers
        dynamic_round = DynamicDebateRound(
            debater_a=debater_a,
            debater_b=debater_b,
            judge=judge,
            ledger=ledger,
            betting=betting,
            distributor=distributor,
            max_iterations=10,
            observers=[metrics_observer],
            split_pot_enabled=True,      # Enable initial bounty distribution
            initial_pot_amount=40.0,     # 40 tokens distributed after initial judgment
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
        
        # Save observations
        if result.observation_reports:
            save_observations(result.observation_reports, "logs/dynamic_observations.json")
            print("\n📊 Observations saved to logs/dynamic_observations.json")
            # Print summary from metrics observer
            for report in result.observation_reports:
                if report.observer_name == "MetricsObserver":
                    print(f"\n--- Metrics Summary ---")
                    print(f"Narrative: {report.narrative}")
                    m = report.metrics
                    print(f"Momentum Shifts: {m.get('momentum_shifts', 0)}")
                    print(f"Debater A: net_chg={m['debater_a']['net_change']:+.0f}, roi={m['debater_a']['roi']}, agg={m['debater_a']['aggression']}")
                    print(f"Debater B: net_chg={m['debater_b']['net_change']:+.0f}, roi={m['debater_b']['roi']}, agg={m['debater_b']['aggression']}")
        
        # Finalize and save transcript
        transcript.finalize(winner, {
            debater_a.name: bal_a,
            debater_b.name: bal_b,
        })
        transcript.save("logs/last_run_transcript.json")
        transcript.save_markdown("logs/last_run_transcript.md")
        print("\nTranscript saved to logs/last_run_transcript.md")
        
    finally:
        debater_a.unload_model()
        debater_b.unload_model()
        judge.unload_model()


if __name__ == "__main__":
    main()
