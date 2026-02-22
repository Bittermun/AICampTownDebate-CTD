#!/usr/bin/env python3
"""
Tournament Insight Distiller
Reads tournament_results.json + tournament_metrics.json and answers the 3 puzzle questions:
  1. Does scarcity change behavior? (pass rate vs balance)
  2. Does betting create quality pressure? (bet size vs judge improvement)
  3. Does elimination create urgency? (performance near bankruptcy)
"""
import json
import sys
from pathlib import Path
from collections import defaultdict

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

RESULTS_FILE = project_root / "logs" / "tournament_results.json"
METRICS_FILE = project_root / "logs" / "tournament_metrics.json"


def load_results():
    if not RESULTS_FILE.exists():
        print(f"[ERROR] Missing {RESULTS_FILE}")
        sys.exit(1)
    with open(RESULTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_metrics():
    if not METRICS_FILE.exists():
        return None
    with open(METRICS_FILE, encoding="utf-8") as f:
        return json.load(f)


def safe(val, fallback=0.0):
    return val if val is not None else fallback


def distill(results: dict, metrics: dict | None):
    rounds = results.get("rounds", [])
    if not rounds:
        print("[ERROR] No rounds found in results")
        return

    debater_a_name = results.get("debater_a", "Debater_A")
    debater_b_name = results.get("debater_b", "Debater_B")

    print("\n" + "=" * 65)
    print("  TOURNAMENT INSIGHT REPORT")
    print("=" * 65)

    # ── 0. Overview ──────────────────────────────────────────────────────────
    winner = results.get("winner") or "TIE"
    final_balances = results.get("final_balances", {})
    eliminated = results.get("eliminated")
    print(f"\n📌 OVERVIEW")
    print(f"  Rounds played   : {len(rounds)}")
    print(f"  Winner          : {winner}")
    if eliminated:
        print(f"  Eliminated (💀) : {eliminated}")
    print(f"  Final balances  : {final_balances}")

    # ── 1. PUZZLE PIECE 1: Does scarcity change behavior? ────────────────────
    print(f"\n🧩 PUZZLE 1 — Does scarcity change behavior?")
    print(f"   (Do debaters PASS more when balance is low?)")

    pass_data = defaultdict(lambda: {"high_bal": {"pass": 0, "respond": 0},
                                      "low_bal":  {"pass": 0, "respond": 0}})

    # We look at per-iteration bets/passes in the round data
    low_threshold = 120   # tokens — below this is "low balance" territory
    for r in rounds:
        bal_a_start = safe(r.get("balance_a_start", r.get("tokens_awarded_a", 200)))
        bal_b_start = safe(r.get("balance_b_start", r.get("tokens_awarded_b", 200)))

        for iteration in r.get("iterations", []):
            action_a = str(iteration.get("action_a", "")).upper()
            action_b = str(iteration.get("action_b", "")).upper()

            bucket_a = "low_bal" if bal_a_start < low_threshold else "high_bal"
            bucket_b = "low_bal" if bal_b_start < low_threshold else "high_bal"

            if action_a in ("PASS", "RESPOND"):
                pass_data[debater_a_name][bucket_a]["pass" if action_a == "PASS" else "respond"] += 1
            if action_b in ("PASS", "RESPOND"):
                pass_data[debater_b_name][bucket_b]["pass" if action_b == "PASS" else "respond"] += 1

    for name, data in pass_data.items():
        for bucket, counts in data.items():
            total = counts["pass"] + counts["respond"]
            if total > 0:
                pass_rate = counts["pass"] / total
                label = "💸 LOW BAL " if bucket == "low_bal" else "   HIGH BAL"
                print(f"  {name[:12]:12s}  {label}: {pass_rate:.0%} pass rate  ({counts['pass']}P/{counts['respond']}R)")

    # ── 2. PUZZLE PIECE 2: Does betting create quality pressure? ─────────────
    print(f"\n🧩 PUZZLE 2 — Does betting create quality pressure?")
    print(f"   (Do rounds with larger bets show bigger confidence shifts?)")

    bet_shift_pairs = []
    for r in rounds:
        bets = r.get("bets", [])
        total_bet = sum(safe(b.get("amount", 0)) for b in bets)
        init_conf_a = safe(r.get("initial_confidence_a", 0.5))
        final_conf_a = safe(r.get("final_confidence_a", 0.5))
        conf_shift = abs(final_conf_a - init_conf_a)
        if total_bet > 0:
            bet_shift_pairs.append((total_bet, conf_shift))

    if bet_shift_pairs:
        # Sort by bet size: compare top half vs bottom half
        bet_shift_pairs.sort(key=lambda x: x[0])
        mid = len(bet_shift_pairs) // 2
        low_bets = bet_shift_pairs[:mid]
        high_bets = bet_shift_pairs[mid:]
        avg_shift_low  = sum(x[1] for x in low_bets)  / len(low_bets)  if low_bets  else 0
        avg_shift_high = sum(x[1] for x in high_bets) / len(high_bets) if high_bets else 0
        avg_bet_low  = sum(x[0] for x in low_bets)  / len(low_bets)  if low_bets  else 0
        avg_bet_high = sum(x[0] for x in high_bets) / len(high_bets) if high_bets else 0
        print(f"  Low-bet rounds  (avg {avg_bet_low:.0f}t): avg confidence shift = {avg_shift_low:.1%}")
        print(f"  High-bet rounds (avg {avg_bet_high:.0f}t): avg confidence shift = {avg_shift_high:.1%}")
        if avg_shift_high > avg_shift_low:
            print(f"  ✅  Higher bets correlate with larger judge shifts (+{(avg_shift_high - avg_shift_low):.1%})")
        else:
            print(f"  ⚠️  No positive correlation between bet size and judge shift")
    else:
        print("  ⚠️  No bet data found in round records")

    # ── 3. PUZZLE PIECE 3: Does urgency emerge near bankruptcy? ──────────────
    print(f"\n🧩 PUZZLE 3 — Does near-bankruptcy change performance?")
    print(f"   (Are confidence improvements larger when a debater is desperate?)")

    normal_improvements = []
    desperate_improvements = []
    desperation_threshold = 100   # tokens

    for r in rounds:
        bal_a = safe(r.get("balance_a_start", 200))
        bal_b = safe(r.get("balance_b_start", 200))
        init_conf_a = safe(r.get("initial_confidence_a", 0.5))
        final_conf_a = safe(r.get("final_confidence_a", 0.5))
        improvement = final_conf_a - init_conf_a

        is_desperate = bal_a < desperation_threshold or bal_b < desperation_threshold
        if is_desperate:
            desperate_improvements.append(improvement)
        else:
            normal_improvements.append(improvement)

    if desperate_improvements and normal_improvements:
        avg_normal = sum(normal_improvements) / len(normal_improvements)
        avg_desperate = sum(desperate_improvements) / len(desperate_improvements)
        print(f"  Normal rounds  ({len(normal_improvements)}): avg conf improvement = {avg_normal:+.1%}")
        print(f"  Desperate rounds ({len(desperate_improvements)}): avg conf improvement = {avg_desperate:+.1%}")
        if avg_desperate > avg_normal:
            print(f"  ✅  Near-bankrupt rounds showed BETTER performance (+{(avg_desperate - avg_normal):.1%})")
        elif avg_desperate < avg_normal - 0.01:
            print(f"  ⚠️  Desperate debaters UNDERPERFORMED ({(avg_normal - avg_desperate):.1%} worse)")
        else:
            print(f"  ➡️  No meaningful difference (within 1% margin)")
    else:
        print(f"  ➡️  Not enough desperate rounds to compare ({len(desperate_improvements)} vs {len(normal_improvements)})")

    # ── 4. Judge Score Spread ─────────────────────────────────────────────────
    print(f"\n📊 JUDGE SPREAD DISTRIBUTION")
    spreads = []
    for r in rounds:
        a = safe(r.get("final_confidence_a", 0.5))
        b = safe(r.get("final_confidence_b", 0.5))
        spreads.append(abs(a - b))

    if spreads:
        avg_spread = sum(spreads) / len(spreads)
        max_spread = max(spreads)
        flat_count = sum(1 for s in spreads if s < 0.10)
        clear_count = sum(1 for s in spreads if s >= 0.20)
        print(f"  Average spread : {avg_spread:.1%}")
        print(f"  Max spread     : {max_spread:.1%}")
        print(f"  Flat rounds (<10%) : {flat_count}/{len(spreads)}")
        print(f"  Clear rounds (≥20%): {clear_count}/{len(spreads)}")

    # ── 5. Economy Summary ────────────────────────────────────────────────────
    print(f"\n💰 ECONOMY SUMMARY")
    total_passes = sum(
        1 for r in rounds for it in r.get("iterations", [])
        if str(it.get("action_a", "")).upper() == "PASS"
        or str(it.get("action_b", "")).upper() == "PASS"
    )
    total_actions = sum(len(r.get("iterations", [])) * 2 for r in rounds)
    if total_actions:
        print(f"  Overall pass rate : {total_passes/total_actions:.0%}  ({total_passes}/{total_actions} actions)")

    print(f"\n{'=' * 65}")
    print("  Done. See logs/tournament_results.json for full detail.")
    print("=" * 65 + "\n")


def main():
    results = load_results()
    metrics = load_metrics()
    distill(results, metrics)


if __name__ == "__main__":
    main()
