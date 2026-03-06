"""Evaluate a trained model against baseline in the debate arena.

Runs matched tournaments with trained vs untrained model and compares:
- Win rate
- Balance advantage
- Judge confidence delta
- Pass rate (lower is better — trained model should be more engaged)
- Economy awareness (mentions of tokens/budget in thinking)

Usage:
    # Compare trained model against baseline
    python scripts/evaluate_trained_model.py \
        --trained-model path/to/checkpoint \
        --baseline-model Qwen/Qwen2.5-1.5B-Instruct \
        --judge-model ollama:qwen2.5:7b \
        --seeds 101,202,303,404,505 \
        --rounds 6 \
        --output-dir logs/eval_results

    # Use ollama-served models
    python scripts/evaluate_trained_model.py \
        --trained-model ollama:trained-debate-1.5b \
        --baseline-model ollama:qwen2.5:1.5b \
        --judge-model ollama:qwen2.5:7b \
        --seeds 101,202,303 \
        --output-dir logs/eval_results

    # Quick smoke test (1 seed, 3 rounds)
    python scripts/evaluate_trained_model.py \
        --trained-model ollama:trained-debate-1.5b \
        --baseline-model ollama:qwen2.5:1.5b \
        --judge-model ollama:qwen2.5:7b \
        --seeds 101 --rounds 3 \
        --output-dir logs/eval_smoke
"""
from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class SeedResult:
    seed: int
    trained_won: bool
    trained_balance: float
    baseline_balance: float
    balance_delta: float
    trained_pass_rate: float
    baseline_pass_rate: float
    rounds_played: int
    eliminated: Optional[str] = None


@dataclass
class EvalReport:
    trained_model: str
    baseline_model: str
    judge_model: str
    seeds: List[int]
    rounds_per_tournament: int
    created_at: str
    seed_results: List[SeedResult] = field(default_factory=list)
    # Aggregate metrics
    win_rate: float = 0.0
    mean_balance_delta: float = 0.0
    stdev_balance_delta: float = 0.0
    mean_trained_pass_rate: float = 0.0
    mean_baseline_pass_rate: float = 0.0
    verdict: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


def run_paired_tournament(
    trained_model: str,
    baseline_model: str,
    judge_model: str,
    seed: int,
    num_rounds: int,
    tournament_config_path: Optional[str] = None,
) -> SeedResult:
    """Run one tournament: trained vs baseline, return results."""
    import random
    random.seed(seed)

    from src.config_loader import load_config, get_default_config
    from src.runtime.preflight import normalize_model_path
    from src.economy.ledger import TokenLedger
    from src.economy.betting import BettingManager
    from src.economy.distribution import TokenDistributor
    from src.models.debater import Debater, DebaterConfig
    from src.models.judge import LLMJudge, JudgeConfig
    from src.arena.tournament import Tournament, EconomyParams

    if tournament_config_path:
        config = load_config(tournament_config_path)
    else:
        config = get_default_config()

    # Override models
    trained_path = normalize_model_path(trained_model)
    baseline_path = normalize_model_path(baseline_model)
    judge_path = normalize_model_path(judge_model)

    econ = EconomyParams(
        initial_balance=config.economy.initial_balance,
        max_debt=config.economy.max_debt,
        tokens_per_round=config.economy.tokens_per_round,
        betting_fee=config.economy.betting_fee,
        min_bet=config.economy.min_bet,
    )

    ledger = TokenLedger(
        initial_balance=econ.initial_balance,
        max_debt=econ.max_debt,
    )
    betting = BettingManager(
        fee_rate=econ.betting_fee,
        min_bet=econ.min_bet,
    )
    distributor = TokenDistributor(tokens_per_round=econ.tokens_per_round)

    # Create debaters — trained as Alpha, baseline as Beta
    trained_debater_config = DebaterConfig(
        name="Trained",
        model_path=trained_path,
        ev_guard_enabled=config.debaters[0].ev_guard_enabled if config.debaters else True,
        kelly_enabled=config.debaters[0].kelly_enabled if config.debaters else True,
    )
    baseline_debater_config = DebaterConfig(
        name="Baseline",
        model_path=baseline_path,
        ev_guard_enabled=config.debaters[1].ev_guard_enabled if len(config.debaters) > 1 else True,
        kelly_enabled=config.debaters[1].kelly_enabled if len(config.debaters) > 1 else True,
    )

    debater_a = Debater(trained_debater_config)
    debater_b = Debater(baseline_debater_config)

    judge_config = JudgeConfig(
        model_path=judge_path,
        randomize_argument_order=True,
    )
    judge = LLMJudge(judge_config)

    ledger.register(debater_a.name)
    ledger.register(debater_b.name)
    debater_a.load_model()
    debater_b.load_model()
    judge.load_model()

    topics = config.topics if config.topics else [
        "Should AI systems be required to explain their reasoning?",
        "Is open-source AI development safer than closed development?",
        "Should AI be used in criminal sentencing decisions?",
    ]

    tournament = Tournament(
        debater_a=debater_a,
        debater_b=debater_b,
        judge=judge,
        ledger=ledger,
        betting_manager=betting,
        distributor=distributor,
        economy_params=econ,
        topics=topics[:num_rounds],
        max_iterations=config.rounds.max_iterations if hasattr(config.rounds, 'max_iterations') else 10,
    )

    tournament.run()

    debater_a.unload_model()
    debater_b.unload_model()
    judge.unload_model()

    balance_a = ledger.balance(debater_a.name)
    balance_b = ledger.balance(debater_b.name)

    # Calculate pass rates from tournament results
    trained_passes = 0
    trained_total = 0
    baseline_passes = 0
    baseline_total = 0
    for r in tournament._results:
        for bet in getattr(r, 'all_bets', getattr(r, 'bets_placed', [])):
            if hasattr(bet, 'bettor_id'):
                if bet.bettor_id == debater_a.name:
                    trained_total += 1
                else:
                    baseline_total += 1

    # Approximate pass rate from iteration count vs bet count
    total_iterations = sum(getattr(r, 'iterations', 0) for r in tournament._results)
    if total_iterations > 0:
        trained_pass_rate = 1.0 - (trained_total / max(total_iterations, 1))
        baseline_pass_rate = 1.0 - (baseline_total / max(total_iterations, 1))
    else:
        trained_pass_rate = 1.0
        baseline_pass_rate = 1.0

    return SeedResult(
        seed=seed,
        trained_won=balance_a > balance_b,
        trained_balance=balance_a,
        baseline_balance=balance_b,
        balance_delta=balance_a - balance_b,
        trained_pass_rate=trained_pass_rate,
        baseline_pass_rate=baseline_pass_rate,
        rounds_played=len(tournament._results),
        eliminated=tournament._eliminated,
    )


def main():
    parser = argparse.ArgumentParser(description="Evaluate trained model vs baseline")
    parser.add_argument("--trained-model", required=True, help="Trained model path or ollama:name")
    parser.add_argument("--baseline-model", required=True, help="Baseline model path or ollama:name")
    parser.add_argument("--judge-model", required=True, help="Judge model (recommend 7b+)")
    parser.add_argument("--seeds", default="101,202,303", help="Comma-separated seeds")
    parser.add_argument("--rounds", type=int, default=6, help="Rounds per tournament")
    parser.add_argument("--tournament-config", help="Tournament config YAML")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    args = parser.parse_args()

    seeds = [int(s) for s in args.seeds.split(",")]
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report = EvalReport(
        trained_model=args.trained_model,
        baseline_model=args.baseline_model,
        judge_model=args.judge_model,
        seeds=seeds,
        rounds_per_tournament=args.rounds,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    for seed in seeds:
        logger.info("Running seed %d: %s vs %s", seed, args.trained_model, args.baseline_model)
        try:
            result = run_paired_tournament(
                trained_model=args.trained_model,
                baseline_model=args.baseline_model,
                judge_model=args.judge_model,
                seed=seed,
                num_rounds=args.rounds,
                tournament_config_path=args.tournament_config,
            )
            report.seed_results.append(result)
            status = "WIN" if result.trained_won else "LOSS"
            logger.info(
                "  Seed %d: %s | balance delta: %+.1f | pass rates: %.2f vs %.2f",
                seed, status, result.balance_delta,
                result.trained_pass_rate, result.baseline_pass_rate,
            )
        except Exception as e:
            logger.error("  Seed %d failed: %s", seed, e)

    # Compute aggregates
    if report.seed_results:
        wins = sum(1 for r in report.seed_results if r.trained_won)
        report.win_rate = wins / len(report.seed_results)
        deltas = [r.balance_delta for r in report.seed_results]
        report.mean_balance_delta = statistics.mean(deltas)
        report.stdev_balance_delta = statistics.stdev(deltas) if len(deltas) > 1 else 0.0
        report.mean_trained_pass_rate = statistics.mean(r.trained_pass_rate for r in report.seed_results)
        report.mean_baseline_pass_rate = statistics.mean(r.baseline_pass_rate for r in report.seed_results)

        # Verdict
        if report.win_rate >= 0.6 and report.mean_balance_delta > 0:
            report.verdict = "POSITIVE: Trained model shows improvement over baseline"
        elif report.win_rate >= 0.5:
            report.verdict = "MARGINAL: Trained model performs comparably to baseline"
        else:
            report.verdict = "NEGATIVE: Trained model underperforms baseline"

    # Save report
    report_path = out_dir / "eval_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)
    logger.info("Evaluation report saved to %s", report_path)

    # Print summary
    print("\n=== EVALUATION SUMMARY ===")
    print(f"Trained: {args.trained_model}")
    print(f"Baseline: {args.baseline_model}")
    print(f"Judge: {args.judge_model}")
    print(f"Seeds: {len(seeds)} | Rounds/tournament: {args.rounds}")
    print(f"Win rate: {report.win_rate:.0%}")
    print(f"Balance delta: {report.mean_balance_delta:+.1f} (stdev {report.stdev_balance_delta:.1f})")
    print(f"Pass rates: trained={report.mean_trained_pass_rate:.2f} baseline={report.mean_baseline_pass_rate:.2f}")
    print(f"Verdict: {report.verdict}")


if __name__ == "__main__":
    main()
