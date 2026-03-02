#!/usr/bin/env python3
"""
Tournament Analysis CLI

Reads any transcript JSON and prints:
  1. Confidence trajectory table (per-round/iteration)
  2. Bet event log (who bet, amount, outcome)
  3. Selection health dashboard
  4. Kelly regret calculation (optimal vs actual bet sizes)

Usage:
    python tests/analyze_tournament.py
    python tests/analyze_tournament.py logs/last_run_transcript.json
    python tests/analyze_tournament.py logs/tournament_results_transcript.json --ledger logs/tournament_results_ledger.json
"""
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.selection_health import compute_selection_health


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def print_confidence_trajectory(transcript: dict):
    """Print confidence scores across all rounds and iterations."""
    print(f"\n{'='*65}")
    print("  CONFIDENCE TRAJECTORY")
    print(f"{'='*65}")
    print(f"  {'Round':>5}  {'Iter':>4}  {'Conf A':>7}  {'Conf B':>7}  {'Margin':>7}  Winner")
    print(f"  {'─'*55}")

    for r in transcript.get("rounds", []):
        round_id = r.get("round_id", "?")
        topic = r.get("topic", "")[:40]
        print(f"\n  Round {round_id}: {topic}...")

        turns = r.get("turns", [])
        judgments = [t for t in turns if t.get("type") == "judgment"]
        for j in judgments:
            ca = float(j.get("confidence_a", 0.5))
            cb = float(j.get("confidence_b", 0.5))
            margin = abs(ca - cb)
            winner = "A" if ca > cb else ("B" if cb > ca else "=")
            iteration = j.get("iteration", "–")
            print(f"  {'':>5}  {str(iteration):>4}  {ca:>7.3f}  {cb:>7.3f}  {margin:>7.3f}  {winner}")


def print_bet_log(transcript: dict):
    """Print all RESPOND decisions with bet amounts and outcomes."""
    print(f"\n{'='*65}")
    print("  BET EVENT LOG")
    print(f"{'='*65}")
    print(f"  {'Round':>5}  {'Debater':<18}  {'Amount':>8}  {'Decision':<10}  {'Outcome'}")
    print(f"  {'─'*55}")

    any_bets = False
    for r in transcript.get("rounds", []):
        round_id = r.get("round_id", "?")
        turns = r.get("turns", [])
        delibs = [t for t in turns if t.get("type") == "deliberation"]
        for t in delibs:
            content = t.get("content", "")
            speaker = t.get("speaker", "?")
            import re
            dec_m = re.search(r"\*\*Decision\*\*:\s*(\w+)", content)
            amt_m = re.search(r"\*\*Bet Amount\*\*:\s*([\d.]+)", content)
            decision = dec_m.group(1) if dec_m else "?"
            amount = float(amt_m.group(1)) if amt_m else 0.0
            if decision.upper() == "RESPOND":
                any_bets = True
                print(f"  {str(round_id):>5}  {speaker:<18}  {amount:>8.1f}  {decision:<10}")

    if not any_bets:
        print("  (no RESPOND bets recorded in this transcript)")


def compute_kelly_regret(transcript: dict) -> float:
    """
    Compute mean Kelly regret: |actual_bet - kelly_optimal_bet| per RESPOND decision.
    kelly_optimal = max(0, conf_self - 0.5) * 0.5 * balance_estimate
    """
    regrets = []
    import re

    for r in transcript.get("rounds", []):
        turns = r.get("turns", [])
        delibs = [t for t in turns if t.get("type") == "deliberation"]
        judgments = [t for t in turns if t.get("type") == "judgment"]
        if not judgments:
            continue
        last_j = judgments[-1]
        ca = float(last_j.get("confidence_a", 0.5))
        cb = float(last_j.get("confidence_b", 0.5))

        for t in delibs:
            content = t.get("content", "")
            dec_m = re.search(r"\*\*Decision\*\*:\s*(\w+)", content)
            amt_m = re.search(r"\*\*Bet Amount\*\*:\s*([\d.]+)", content)
            bal_m = re.search(r"balance[:\s]+([\d.]+)", content, re.IGNORECASE)
            if not dec_m or dec_m.group(1).upper() != "RESPOND":
                continue
            actual = float(amt_m.group(1)) if amt_m else 0.0
            balance = float(bal_m.group(1)) if bal_m else 200.0
            speaker = t.get("speaker", "")
            conf_self = ca if "Alpha" in speaker else cb
            edge = max(0.0, conf_self - 0.5)
            kelly_opt = edge * 0.5 * balance  # half-Kelly
            regrets.append(abs(actual - kelly_opt))

    return sum(regrets) / len(regrets) if regrets else 0.0


def print_health_dashboard(transcript: dict, ledger: dict | None):
    health = compute_selection_health(transcript, ledger=ledger)
    print(f"\n{'='*65}")
    print("  SELECTION HEALTH DASHBOARD")
    print(f"{'='*65}")
    print(f"  Health Score:        {health.health_score:.3f}  (0=degenerate → 1=ideal)")
    print(f"  Judge Margin Mean:   {health.judge_margin_mean:.3f}  stdev={health.judge_margin_stdev:.3f}")
    print(f"  Adaptation (↑loss):  {health.adaptation_gain_after_loss:+.3f}")
    print(f"  Economy Reasoning:   {health.economy_reasoning_rate:.1%}")
    print(f"  Pass Rate:           {health.pass_rate:.1%}  (target ~35%)")
    print(f"  Aggression Rate:     {health.aggression_rate:.1%}")
    print(f"  Avg Iterations:      {health.avg_iterations:.1f}")
    print(f"  Score Entropy:       {health.judge_score_entropy_bits:.2f} bits")
    print(f"  Mutual Pass Rounds:  {health.mutual_pass_round_rate:.1%}")
    print(f"  Survival Runway:     {health.survival_runway_observed:.1f} rounds")
    print(f"{'='*65}")


def main():
    parser = argparse.ArgumentParser(description="Analyze tournament transcript")
    parser.add_argument(
        "transcript",
        nargs="?",
        default="logs/last_run_transcript.json",
        help="Path to transcript JSON",
    )
    parser.add_argument("--ledger", default=None, help="Path to ledger JSON")
    args = parser.parse_args()

    transcript_path = args.transcript
    if not Path(transcript_path).exists():
        fallback = "logs/tournament_results_transcript.json"
        if Path(fallback).exists():
            transcript_path = fallback
            print(f"[INFO] Using fallback: {fallback}")
        else:
            print(f"[ERROR] Transcript not found: {args.transcript}")
            sys.exit(1)

    transcript = load_json(transcript_path)

    # Auto-detect ledger
    ledger = None
    ledger_path = args.ledger or str(Path(transcript_path).with_suffix("").with_name(
        Path(transcript_path).stem.replace("_transcript", "_ledger") + ".json"
    ))
    if Path(ledger_path).exists():
        ledger = load_json(ledger_path)

    print(f"\nAnalyzing: {transcript_path}")
    if ledger:
        print(f"Ledger:    {ledger_path}")

    print_confidence_trajectory(transcript)
    print_bet_log(transcript)

    kelly_regret = compute_kelly_regret(transcript)
    print(f"\n{'='*65}")
    print(f"  KELLY REGRET")
    print(f"{'='*65}")
    print(f"  Mean |actual_bet - kelly_optimal|: {kelly_regret:.2f} tokens")
    if kelly_regret < 3:
        print("  → Bets are near-optimal (very good)")
    elif kelly_regret < 10:
        print("  → Bets are reasonable but improvable")
    else:
        print("  → Bets are far from optimal (economic strategy needs work)")
    print(f"{'='*65}")

    print_health_dashboard(transcript, ledger)


if __name__ == "__main__":
    main()
