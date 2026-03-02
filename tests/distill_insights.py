#!/usr/bin/env python3
"""
Tournament Insight Distiller
Reads tournament_results.json + tournament_metrics.json and answers the 3 puzzle questions.
"""
import json
import sys
import re
from pathlib import Path
from collections import defaultdict

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

RESULTS_FILE = project_root / "logs" / "tournament_results.json"
TRANSCRIPT_FILE = project_root / "logs" / "tournament_results_transcript.json"

def load_json(path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def safe(val, fallback=0.0):
    return val if val is not None else fallback

def distill():
    results = load_json(RESULTS_FILE)
    transcript = load_json(TRANSCRIPT_FILE)
    if not transcript or not results:
        print("[ERROR] Missing results or transcript json")
        return

    rounds = transcript.get("rounds", [])
    if not rounds:
        print("[ERROR] No rounds found in transcript")
        return

    debater_a_name = results.get("config", {}).get("debater_a", "Debater_A")
    debater_b_name = results.get("config", {}).get("debater_b", "Debater_B")
    
    cfg = transcript.get("config", {})
    if "debater_a" in cfg:
        debater_a_name = cfg["debater_a"]
        debater_b_name = cfg["debater_b"]

    print("\n" + "=" * 65)
    print("  TOURNAMENT INSIGHT REPORT")
    print("=" * 65)

    winner = transcript.get("winner") or "TIE"
    final_balances = transcript.get("final_balances", {})
    eliminated = results.get("eliminated")
    print(f"\n📌 OVERVIEW")
    print(f"  Rounds played   : {len(rounds)}")
    print(f"  Winner          : {winner}")
    if eliminated:
        print(f"  Eliminated (💀) : {eliminated}")
    print(f"  Final balances  : {final_balances}")

    print(f"\n🧩 PUZZLE 1 — Does scarcity change behavior?")
    print(f"   (Do debaters PASS more when balance is low?)")
    
    pass_data = defaultdict(lambda: {"high_bal": {"pass": 0, "respond": 0},
                                      "low_bal":  {"pass": 0, "respond": 0}})

    low_threshold = 120
    total_passes = 0
    total_actions = 0

    bet_shift_pairs = []
    normal_improvements = []
    desperate_improvements = []
    desperation_threshold = 100
    spreads = []

    for r in rounds:
        turns = r.get("turns", [])
        
        judgments = [t for t in turns if t.get("type") == "judgment"]
        if not judgments:
            continue
            
        init_conf_a = safe(judgments[0].get("confidence_a", 0.5))
        final_conf_a = safe(judgments[-1].get("confidence_a", 0.5))
        spreads.append(abs(final_conf_a - judgments[-1].get("confidence_b", 0.5)))
        improvement_a = final_conf_a - init_conf_a

        delibs = [t for t in turns if t.get("type") == "deliberation"]
        
        bal_a_start = 200
        bal_b_start = 200
        bal_a_found = False
        bal_b_found = False
        for d in delibs:
            if d.get("speaker") == debater_a_name and not bal_a_found:
                content = d.get("content", "")
                m = re.search(r"\*\*Balance\*\*: ([\d\.-]+)", content)
                if m: bal_a_start = float(m.group(1))
                bal_a_found = True
            elif d.get("speaker") == debater_b_name and not bal_b_found:
                content = d.get("content", "")
                m = re.search(r"\*\*Balance\*\*: ([\d\.-]+)", content)
                if m: bal_b_start = float(m.group(1))
                bal_b_found = True

        is_desperate = bal_a_start < desperation_threshold or bal_b_start < desperation_threshold
        if is_desperate:
            desperate_improvements.append(improvement_a)
        else:
            normal_improvements.append(improvement_a)
            
        round_bet_total = 0
        for d in delibs:
            speaker = d.get("speaker", "")
            content = d.get("content", "")
            
            action = "PASS" if ("Decision**: PASS" in content or "Decision**: HOLD" in content) else "RESPOND"
            
            m_bal = re.search(r"\*\*Balance\*\*: ([\d\.-]+)", content)
            bal = float(m_bal.group(1)) if m_bal else 200
            
            m_bet = re.search(r"\(bet: ([\d\.-]+) tokens\)", content)
            amount = float(m_bet.group(1)) if m_bet else 0
            
            round_bet_total += amount
            
            bucket = "low_bal" if bal < low_threshold else "high_bal"
            if action == "PASS":
                pass_data[speaker][bucket]["pass"] += 1
                total_passes += 1
            else:
                pass_data[speaker][bucket]["respond"] += 1
            total_actions += 1

        conf_shift = abs(final_conf_a - init_conf_a)
        if round_bet_total > 0:
            bet_shift_pairs.append((round_bet_total, conf_shift))

    for name, data in pass_data.items():
        for bucket, counts in data.items():
            total = counts["pass"] + counts["respond"]
            if total > 0:
                pass_rate = counts["pass"] / total
                label = "💸 LOW BAL " if bucket == "low_bal" else "   HIGH BAL"
                print(f"  {name[:12]:12s}  {label}: {pass_rate:.0%} pass rate  ({counts['pass']}P/{counts['respond']}R)")

    print(f"\n🧩 PUZZLE 2 — Does betting create quality pressure?")
    print(f"   (Do rounds with larger bets show bigger confidence shifts?)")
    if bet_shift_pairs:
        bet_shift_pairs.sort(key=lambda x: x[0])
        mid = len(bet_shift_pairs) // 2
        low_bets = bet_shift_pairs[:mid]
        high_bets = bet_shift_pairs[mid:]
        
        avg_shift_low  = sum(x[1] for x in low_bets)  / len(low_bets)  if low_bets  else 0
        avg_shift_high = sum(x[1] for x in high_bets) / len(high_bets) if high_bets else 0
        avg_bet_low  = sum(x[0] for x in low_bets)  / len(low_bets)  if low_bets  else 0
        avg_bet_high = sum(x[0] for x in high_bets) / len(high_bets) if high_bets else 0
        
        if len(bet_shift_pairs) == 1:
            print(f"  Only 1 round with bet: {bet_shift_pairs[0][0]:.0f} tokens, shift: {bet_shift_pairs[0][1]:.1%}")
        else:
            print(f"  Low-bet rounds  (avg {avg_bet_low:.0f}t): avg confidence shift = {avg_shift_low:.1%}")
            print(f"  High-bet rounds (avg {avg_bet_high:.0f}t): avg confidence shift = {avg_shift_high:.1%}")
            if avg_shift_high > avg_shift_low:
                print(f"  ✅  Higher bets correlate with larger judge shifts (+{(avg_shift_high - avg_shift_low):.1%})")
            else:
                print(f"  ⚠️  No positive correlation between bet size and judge shift")
    else:
        print("  ⚠️  No bet data found in round records")

    print(f"\n🧩 PUZZLE 3 — Does near-bankruptcy change performance?")
    print(f"   (Are confidence improvements larger when a debater is desperate?)")
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

    print(f"\n📊 JUDGE SPREAD DISTRIBUTION")
    if spreads:
        avg_spread = sum(spreads) / len(spreads)
        max_spread = max(spreads)
        flat_count = sum(1 for s in spreads if s < 0.10)
        clear_count = sum(1 for s in spreads if s >= 0.20)
        print(f"  Average spread : {avg_spread:.1%}")
        print(f"  Max spread     : {max_spread:.1%}")
        print(f"  Flat rounds (<10%) : {flat_count}/{len(spreads)}")
        print(f"  Clear rounds (≥20%): {clear_count}/{len(spreads)}")

    print(f"\n💰 ECONOMY SUMMARY")
    if total_actions:
        print(f"  Overall pass rate : {total_passes/total_actions:.0%}  ({total_passes}/{total_actions} actions)")

    print(f"\n{'=' * 65}")
    print("  Done. See logs/tournament_results_transcript.json")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    distill()
