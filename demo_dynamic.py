"""
Demo: Run a dynamic debate (AI-driven duration).
Usage:
  python demo_dynamic.py                               # Uses defaults
  python demo_dynamic.py --config path/to/config.yaml  # Uses config file
"""
import argparse

from src.models import Debater, DebaterConfig, Judge, JudgeConfig
from src.arena import DynamicDebateRound, EconomyParams
from src.arena.observers import MetricsObserver, HealthCheckObserver, save_observations
from src.economy import TokenLedger, BettingManager, TokenDistributor
from src.logs import create_transcript
from src.config_loader import load_config, get_default_config
from src.runtime import normalize_model_path, run_preflight, print_preflight


def main():
    parser = argparse.ArgumentParser(description="Run a dynamic debate")
    parser.add_argument("--config", type=str, help="Path to tournament config YAML")
    parser.add_argument("model", nargs="?", default=None, help="Fallback model (legacy)")
    parser.add_argument(
        "--allow-stub",
        action="store_true",
        help="Allow stub backend or backend fallback (unsafe for real experiment data)",
    )
    args = parser.parse_args()

    if args.config:
        print(f"Loading config from: {args.config}")
        tc = load_config(args.config)
    else:
        tc = get_default_config()
        if args.model:
            for d in tc.debaters:
                d.model = args.model
            for j in tc.judges:
                j.model = args.model

    print("=" * 60)
    print("DYNAMIC DEBATE EXPERIMENT - AI-DRIVEN DURATION")
    print("=" * 60)

    model_specs = [
        ("Debater A", tc.debaters[0].model),
        ("Debater B", tc.debaters[1].model),
        ("Judge", tc.judges[0].model),
    ]
    try:
        preflight = run_preflight(
            model_specs,
            allow_stub=args.allow_stub,
            allow_backend_fallback=args.allow_stub,
        )
    except RuntimeError as e:
        print(str(e))
        return
    print_preflight(preflight)

    print(f"Debaters: {', '.join(f'{d.name}@{d.model}' for d in tc.debaters)}")
    print(f"Judge: {tc.judges[0].model if tc.judges else 'default'}")

    topic = tc.rounds.topics[0] if tc.rounds.topics else "Should AI development be regulated?"
    print(f"\nTopic: {topic}")
    print("Mode: Dynamic (continues until both debaters PASS)")
    print(f"Max iterations: {tc.rounds.max_iterations}")

    economy_params = EconomyParams(
        initial_balance=tc.economy.initial_balance,
        max_debt=tc.economy.max_debt,
        tokens_per_round=tc.economy.tokens_per_round,
    )

    ledger = TokenLedger(economy_params.initial_balance, economy_params.max_debt)
    betting = BettingManager(economy_params.betting_fee, economy_params.min_bet)
    distributor = TokenDistributor(economy_params.tokens_per_round)

    debater_a = Debater(DebaterConfig(
        model_path=normalize_model_path(tc.debaters[0].model),
        name=f"Debater_{tc.debaters[0].name}",
        system_prompt=tc.debaters[0].system_prompt,
        ev_guard_enabled=tc.debaters[0].ev_guard_enabled,
        ev_guard_min_ev=tc.debaters[0].ev_guard_min_ev,
        ev_guard_edge_scale=tc.debaters[0].ev_guard_edge_scale,
        low_balance_threshold=tc.debaters[0].low_balance_threshold,
        low_balance_bet_cap=tc.debaters[0].low_balance_bet_cap,
    ))
    debater_b = Debater(DebaterConfig(
        model_path=normalize_model_path(tc.debaters[1].model),
        name=f"Debater_{tc.debaters[1].name}",
        system_prompt=tc.debaters[1].system_prompt,
        ev_guard_enabled=tc.debaters[1].ev_guard_enabled,
        ev_guard_min_ev=tc.debaters[1].ev_guard_min_ev,
        ev_guard_edge_scale=tc.debaters[1].ev_guard_edge_scale,
        low_balance_threshold=tc.debaters[1].low_balance_threshold,
        low_balance_bet_cap=tc.debaters[1].low_balance_bet_cap,
    ))

    from src.models.judge import EnsembleJudge, ConsensusJudge, LLMJudge

    if tc.judge_type == "consensus" and len(tc.judges) > 1:
        sub_judges = []
        for i, j_spec in enumerate(tc.judges):
            sub_judge = LLMJudge(JudgeConfig(
                model_path=normalize_model_path(j_spec.model),
                name=j_spec.name or f"Judge_{i+1}",
                randomize_argument_order=tc.randomize_argument_order,
            ))
            sub_judges.append(sub_judge)

        instructor_model = tc.instructor_model or tc.judges[0].model
        instructor = LLMJudge(JudgeConfig(
            model_path=normalize_model_path(instructor_model),
            name="Lead_Instructor",
            randomize_argument_order=tc.randomize_argument_order,
        ))
        judge = ConsensusJudge(sub_judges, instructor, name="Consensus_Judge")
        print(f"Created consensus with {len(sub_judges)} sub-judges + instructor")
    elif tc.judge_type == "ensemble" or len(tc.judges) > 1:
        sub_judges = []
        for i, j_spec in enumerate(tc.judges):
            sub_judge = LLMJudge(JudgeConfig(
                model_path=normalize_model_path(j_spec.model),
                name=j_spec.name or f"Judge_{i+1}",
                randomize_argument_order=tc.randomize_argument_order,
            ))
            sub_judges.append(sub_judge)
        judge = EnsembleJudge(sub_judges, name="Ensemble_Judge")
        print(f"Created ensemble with {len(sub_judges)} judges (averaging)")
    else:
        judge = Judge(JudgeConfig(
            model_path=normalize_model_path(tc.judges[0].model),
            name=tc.judges[0].name or "Judge_Main",
            randomize_argument_order=tc.randomize_argument_order,
        ))

    metrics_observer = MetricsObserver()
    health_observer = HealthCheckObserver()

    ledger.register(debater_a.name)
    ledger.register(debater_b.name)

    debater_a.load_model()
    debater_b.load_model()
    judge.load_model()

    transcript = create_transcript({
        "mode": "dynamic",
        "initial_balance": economy_params.initial_balance,
        "max_debt": economy_params.max_debt,
        "max_iterations": tc.rounds.max_iterations,
        "debater_a": debater_a.name,
        "debater_b": debater_b.name,
        "judge": judge.name,
    })
    round_transcript = transcript.new_round(1, topic)

    try:
        dynamic_round = DynamicDebateRound(
            debater_a=debater_a,
            debater_b=debater_b,
            judge=judge,
            ledger=ledger,
            betting=betting,
            distributor=distributor,
            max_iterations=tc.rounds.max_iterations,
            observers=[metrics_observer, health_observer],
            split_pot_enabled=tc.economy.split_pot_enabled,
            initial_pot_amount=tc.economy.initial_pot_amount,
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
        print("Final Balances:")
        print(f"  {debater_a.name}: {ledger.balance(debater_a.name):.1f} tokens")
        print(f"  {debater_b.name}: {ledger.balance(debater_b.name):.1f} tokens")

        bal_a = ledger.balance(debater_a.name)
        bal_b = ledger.balance(debater_b.name)
        if bal_a > bal_b:
            winner = debater_a.name
        elif bal_b > bal_a:
            winner = debater_b.name
        else:
            winner = None

        print(f"\nWinner: {winner or 'TIE'}")

        if result.observation_reports:
            save_observations(result.observation_reports, "logs/dynamic_observations.json")
            print("\nObservations saved to logs/dynamic_observations.json")
            for report in result.observation_reports:
                if report.observer_name == "MetricsObserver":
                    print("\n--- Metrics Summary ---")
                    print(f"Narrative: {report.narrative}")
                    m = report.metrics
                    print(f"Momentum Shifts: {m.get('momentum_shifts', 0)}")
                    print(f"Debater A: net_chg={m['debater_a']['net_change']:+.0f}, roi={m['debater_a']['roi']}, agg={m['debater_a']['aggression']}")
                    print(f"Debater B: net_chg={m['debater_b']['net_change']:+.0f}, roi={m['debater_b']['roi']}, agg={m['debater_b']['aggression']}")

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
