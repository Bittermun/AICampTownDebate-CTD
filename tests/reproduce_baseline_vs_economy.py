#!/usr/bin/env python3
"""Run paired baseline-vs-economy tournaments and compare outcomes."""
import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config_loader import load_config
from src.models import Debater, DebaterConfig
from src.models.judge import LLMJudge, JudgeConfig
from src.arena.tournament import Tournament, EconomyParams
from src.arena.observers import MetricsObserver
from src.runtime import normalize_model_path, run_preflight, print_preflight


def build_participants(cfg):
    debater_a = Debater(DebaterConfig(
        model_path=normalize_model_path(cfg.debaters[0].model),
        name=f"Debater_{cfg.debaters[0].name}",
        system_prompt=cfg.debaters[0].system_prompt,
    ))
    debater_b = Debater(DebaterConfig(
        model_path=normalize_model_path(cfg.debaters[1].model),
        name=f"Debater_{cfg.debaters[1].name}",
        system_prompt=cfg.debaters[1].system_prompt,
    ))
    judge = LLMJudge(JudgeConfig(
        model_path=normalize_model_path(cfg.judges[0].model),
        name="Judge_Main",
        randomize_argument_order=cfg.randomize_argument_order,
    ))
    return debater_a, debater_b, judge


def summarize_round_metrics(rounds):
    agg_a = 0.0
    agg_b = 0.0
    pass_a = 0.0
    pass_b = 0.0
    count = 0
    for r in rounds:
        for rep in getattr(r, "observation_reports", []):
            if rep.observer_name == "MetricsObserver":
                m = rep.metrics
                agg_a += m["debater_a"]["aggression"]
                agg_b += m["debater_b"]["aggression"]
                pass_a += m["debater_a"]["pass_rate"]
                pass_b += m["debater_b"]["pass_rate"]
                count += 1
    if count == 0:
        return {}
    return {
        "avg_aggression_a": round(agg_a / count, 3),
        "avg_aggression_b": round(agg_b / count, 3),
        "avg_pass_rate_a": round(pass_a / count, 3),
        "avg_pass_rate_b": round(pass_b / count, 3),
    }


def run_condition(cfg, mode_name: str, baseline: bool = False):
    debater_a, debater_b, judge = build_participants(cfg)
    observer = MetricsObserver()

    if baseline:
        econ = EconomyParams(
            num_rounds=cfg.rounds.num_rounds,
            max_iterations=cfg.rounds.max_iterations,
            initial_balance=max(cfg.economy.initial_balance, 1000),
            max_debt=max(cfg.economy.max_debt, 200),
            tokens_per_round=0,
            betting_fee=0.0,
            min_bet=5.0,
        )
        split_pot_enabled = False
        initial_pot_amount = 0.0
    else:
        econ = EconomyParams(
            num_rounds=cfg.rounds.num_rounds,
            max_iterations=cfg.rounds.max_iterations,
            initial_balance=cfg.economy.initial_balance,
            max_debt=cfg.economy.max_debt,
            tokens_per_round=cfg.economy.tokens_per_round,
            betting_fee=0.05,
            min_bet=5.0,
        )
        split_pot_enabled = cfg.economy.split_pot_enabled
        initial_pot_amount = cfg.economy.initial_pot_amount

    tournament = Tournament(
        debater_a=debater_a,
        debater_b=debater_b,
        judge=judge,
        topics=cfg.rounds.topics,
        config=econ,
        enable_transcript=False,
        observers=[observer],
        split_pot_enabled=split_pot_enabled,
        initial_pot_amount=initial_pot_amount,
    )
    result = tournament.run()

    metrics = summarize_round_metrics(result.rounds)
    return {
        "mode": mode_name,
        "winner": result.winner,
        "final_balances": result.final_balances,
        "rounds_completed": len(result.rounds),
        **metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Paired baseline-vs-economy experiment")
    parser.add_argument("--config", default="configs/tournament_config.yaml")
    parser.add_argument("--rounds", type=int, default=3, help="Override rounds for faster runs")
    parser.add_argument("--allow-stub", action="store_true")
    parser.add_argument("--output", default="logs/baseline_vs_economy.json")
    args = parser.parse_args()

    cfg = load_config(args.config)
    cfg.rounds.num_rounds = max(1, args.rounds)
    cfg.rounds.topics = cfg.rounds.topics[: cfg.rounds.num_rounds]

    model_specs = [
        ("Debater A", cfg.debaters[0].model),
        ("Debater B", cfg.debaters[1].model),
        ("Judge", cfg.judges[0].model),
    ]
    try:
        preflight = run_preflight(
            model_specs,
            allow_stub=args.allow_stub,
            allow_backend_fallback=args.allow_stub,
        )
    except RuntimeError as e:
        print(str(e))
        return 1
    print_preflight(preflight)

    base_cfg = deepcopy(cfg)
    econ_cfg = deepcopy(cfg)

    print("\nRunning baseline condition...")
    baseline = run_condition(base_cfg, "baseline", baseline=True)

    print("\nRunning economy condition...")
    economy = run_condition(econ_cfg, "economy", baseline=False)

    report = {
        "config": args.config,
        "rounds": cfg.rounds.num_rounds,
        "baseline": baseline,
        "economy": economy,
        "delta": {
            "balance_spread_baseline": abs(
                baseline["final_balances"].get("Debater_Alpha", 0) - baseline["final_balances"].get("Debater_Beta", 0)
            ),
            "balance_spread_economy": abs(
                economy["final_balances"].get("Debater_Alpha", 0) - economy["final_balances"].get("Debater_Beta", 0)
            ),
            "avg_pass_rate_a_delta": economy.get("avg_pass_rate_a", 0) - baseline.get("avg_pass_rate_a", 0),
            "avg_pass_rate_b_delta": economy.get("avg_pass_rate_b", 0) - baseline.get("avg_pass_rate_b", 0),
        },
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nSaved comparison report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
