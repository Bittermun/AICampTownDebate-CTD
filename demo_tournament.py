#!/usr/bin/env python3
"""
Demo: Multi-Round Tournament with DynamicDebateRound

Run with:
    python demo_tournament.py --config configs/tournament_config.yaml
"""

import argparse
from pathlib import Path

import json
from src.config_loader import load_config, get_default_config
from src.models import Debater, DebaterConfig
from src.models.judge import LLMJudge, JudgeConfig, EnsembleJudge, ConsensusJudge
from src.arena.tournament import Tournament, EconomyParams
from src.arena.observers import MetricsObserver
from src.runtime import normalize_model_path, run_preflight, print_preflight
from src.analysis import evaluate_judge_variance, evaluate_judge_calibration
from src.analysis.selection_health import compute_selection_health
from src.integrations.match_registry import MatchRegistry


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
    parser.add_argument(
        "--allow-stub",
        action="store_true",
        help="Allow stub backend or fallback (unsafe for real experiment data)",
    )
    parser.add_argument(
        "--gate-judge-variance",
        action="store_true",
        help="Run judge variance gate before tournament and abort on failure",
    )
    parser.add_argument("--variance-runs", type=int, default=10)
    parser.add_argument("--max-judge-stdev", type=float, default=0.05)
    parser.add_argument("--min-judge-mean-a", type=float, default=0.55)
    parser.add_argument(
        "--gate-judge-calibration",
        action="store_true",
        help="Run fixed-case calibration gate before tournament and abort on failure",
    )
    parser.add_argument("--min-calibration-pass-rate", type=float, default=0.67)
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

    model_specs = [
        ("Debater A", cfg.debaters[0].model),
        ("Debater B", cfg.debaters[1].model),
    ]
    for i, j in enumerate(cfg.judges, start=1):
        model_specs.append((f"Judge {i}", j.model))
    if cfg.judge_type == "consensus" and cfg.instructor_model:
        model_specs.append(("Instructor", cfg.instructor_model))
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
    
    # Create debaters using DebaterConfig
    debater_a = Debater(DebaterConfig(
        model_path=normalize_model_path(cfg.debaters[0].model),
        name=f"Debater_{cfg.debaters[0].name}",
        strict_runtime=not args.allow_stub,
        system_prompt=cfg.debaters[0].system_prompt,
        ev_guard_enabled=cfg.debaters[0].ev_guard_enabled,
        ev_guard_min_ev=cfg.debaters[0].ev_guard_min_ev,
        ev_guard_edge_scale=cfg.debaters[0].ev_guard_edge_scale,
        low_balance_threshold=cfg.debaters[0].low_balance_threshold,
        low_balance_bet_cap=cfg.debaters[0].low_balance_bet_cap,
    ))
    debater_b = Debater(DebaterConfig(
        model_path=normalize_model_path(cfg.debaters[1].model),
        name=f"Debater_{cfg.debaters[1].name}",
        strict_runtime=not args.allow_stub,
        system_prompt=cfg.debaters[1].system_prompt,
        ev_guard_enabled=cfg.debaters[1].ev_guard_enabled,
        ev_guard_min_ev=cfg.debaters[1].ev_guard_min_ev,
        ev_guard_edge_scale=cfg.debaters[1].ev_guard_edge_scale,
        low_balance_threshold=cfg.debaters[1].low_balance_threshold,
        low_balance_bet_cap=cfg.debaters[1].low_balance_bet_cap,
    ))
    
    # Create judge(s) from config
    if cfg.judge_type == "consensus" and len(cfg.judges) > 1:
        sub_judges = []
        for i, j_spec in enumerate(cfg.judges, start=1):
            sub_judges.append(LLMJudge(JudgeConfig(
                model_path=normalize_model_path(j_spec.model),
                name=j_spec.name or f"Judge_{i}",
                randomize_argument_order=cfg.randomize_argument_order,
                strict_runtime=not args.allow_stub,
            )))
        instructor_model = cfg.instructor_model or cfg.judges[0].model
        instructor = LLMJudge(JudgeConfig(
            model_path=normalize_model_path(instructor_model),
            name="Lead_Instructor",
            randomize_argument_order=cfg.randomize_argument_order,
            strict_runtime=not args.allow_stub,
        ))
        judge = ConsensusJudge(sub_judges, instructor, name="Consensus_Judge")
        judge_config = JudgeConfig(model_path=normalize_model_path(instructor_model), name="Lead_Instructor")
    elif cfg.judge_type == "ensemble" or len(cfg.judges) > 1:
        sub_judges = []
        for i, j_spec in enumerate(cfg.judges, start=1):
            sub_judges.append(LLMJudge(JudgeConfig(
                model_path=normalize_model_path(j_spec.model),
                name=j_spec.name or f"Judge_{i}",
                randomize_argument_order=cfg.randomize_argument_order,
                strict_runtime=not args.allow_stub,
            )))
        judge = EnsembleJudge(sub_judges, name="Ensemble_Judge")
        judge_config = JudgeConfig(model_path=normalize_model_path(cfg.judges[0].model), name="Judge_1")
    else:
        judge_config = JudgeConfig(
            model_path=normalize_model_path(cfg.judges[0].model),
            name=cfg.judges[0].name or "Judge_Main",
            randomize_argument_order=cfg.randomize_argument_order,
            strict_runtime=not args.allow_stub,
        )
        judge = LLMJudge(config=judge_config)

    if args.gate_judge_variance:
        print("\nRunning judge variance gate...")
        gate_config = JudgeConfig(
            model_path=judge_config.model_path,
            name=f"{judge_config.name}_gate",
            randomize_argument_order=False,  # Disable shuffling for repeatability gate
            strict_runtime=not args.allow_stub,
        )
        gate_judge = LLMJudge(config=gate_config)
        gate_judge.load_model()
        try:
            gate = evaluate_judge_variance(
                judge=gate_judge,
                topic="Should humans colonize Mars?",
                argument_a=(
                    "I accept your radiation concern; that is exactly why we should begin now "
                    "to solve shielding before stakes are higher."
                ),
                argument_b=(
                    "Mars is too expensive and barren. We should stay on Earth. Mars is too expensive."
                ),
                runs=args.variance_runs,
                max_stdev=args.max_judge_stdev,
                min_mean_a=args.min_judge_mean_a,
                round_id=1,
            )
        finally:
            gate_judge.unload_model()
        print(
            f"Judge gate: pass={gate.passed} mean_a={gate.mean_confidence_a:.3f} "
            f"stdev={gate.stdev_confidence_a:.3f}"
        )
        if not gate.passed:
            print("Aborting tournament: judge variance gate failed.")
            return

    if args.gate_judge_calibration:
        print("\nRunning judge calibration gate...")
        cal_config = JudgeConfig(
            model_path=judge_config.model_path,
            name=f"{judge_config.name}_calibration",
            randomize_argument_order=False,
            strict_runtime=not args.allow_stub,
        )
        cal_judge = LLMJudge(config=cal_config)
        cal_judge.load_model()
        try:
            cal = evaluate_judge_calibration(
                judge=cal_judge,
                pass_threshold=args.min_calibration_pass_rate,
                round_id=1000,
            )
        finally:
            cal_judge.unload_model()
        print(
            f"Judge calibration: pass={cal.passed} "
            f"pass_rate={cal.pass_rate:.3f} threshold={cal.pass_threshold:.3f}"
        )
        if not cal.passed:
            print("Aborting tournament: judge calibration gate failed.")
            return
    
    # Create observer
    observer = MetricsObserver()
    
    # Build economy params
    economy_params = EconomyParams(
        num_rounds=cfg.rounds.num_rounds,
        max_iterations=cfg.rounds.max_iterations,
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

    # ── Selection Health Dashboard ─────────────────────────────────────────────
    try:
        transcript_path = output_dir / "tournament_results_transcript.json"
        ledger_path = output_dir / "tournament_results_ledger.json"
        if transcript_path.exists():
            with open(transcript_path, encoding="utf-8") as f:
                transcript_data = json.load(f)
            ledger_data = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else None
            health = compute_selection_health(transcript_data, ledger=ledger_data)
            print(f"\n{'─'*60}")
            print("  SELECTION HEALTH DASHBOARD")
            print(f"{'─'*60}")
            print(f"  Health Score:        {health.health_score:.3f}  (0=degenerate, 1=ideal)")
            print(f"  Judge Margin Mean:   {health.judge_margin_mean:.3f}  stdev={health.judge_margin_stdev:.3f}")
            print(f"  Adaptation (↑loss):  {health.adaptation_gain_after_loss:+.3f}  (positive = recovery)")
            print(f"  Economy Reasoning:   {health.economy_reasoning_rate:.1%}  (deliberation mentions tokens/budget)")
            print(f"  Pass Rate:           {health.pass_rate:.1%}  (target ~35%)")
            print(f"  Aggression Rate:     {health.aggression_rate:.1%}")
            print(f"  Avg Iterations:      {health.avg_iterations:.1f}")
            print(f"  Judge Score Entropy: {health.judge_score_entropy_bits:.2f} bits  (higher = richer signal)")
            print(f"{'─'*60}")
    except Exception as e:
        print(f"  [Health dashboard error: {e}]")

    # ── Match Registry — persistent cross-session storage ─────────────────────
    try:
        registry = MatchRegistry()
        config_label = getattr(args, "config", None) or f"default_{args.model}"
        run_id = registry.log_tournament(
            result,
            health_report=health if "health" in dir() else None,
            config_label=config_label,
        )
        registry.print_leaderboard(limit=5)
    except Exception as e:
        print(f"  [Match registry error: {e}]")

    print(f"\nResults saved to {output_dir}")


if __name__ == "__main__":
    main()
