#!/usr/bin/env python3
"""
Compare two batch run directories and print a summary table.
Usage: python scripts/compare_batch_results.py <dir_a> <dir_b> [--label-a NAME] [--label-b NAME]
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from statistics import mean, stdev


def load_manifest(root: Path) -> dict | None:
    p = root / "batch_manifest.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    # Fall back to scanning summary jsonl
    p2 = root / "batch_summary.jsonl"
    if not p2.exists():
        # Try finding it recursively
        candidates = list(root.rglob("batch_manifest.json"))
        if candidates:
            return json.loads(candidates[0].read_text(encoding="utf-8"))
        candidates = list(root.rglob("batch_summary.jsonl"))
        if candidates:
            p2 = candidates[0]
        else:
            return None
    records = []
    for line in p2.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and "run_no" in obj:
                records.append(obj)
        except Exception:
            continue
    return {"records": records, "aggregate": {}}


def compute_stats(records: list[dict]) -> dict:
    successes = [r for r in records if r.get("success")]
    if not successes:
        return {"runs": len(records), "success_rate": 0.0}

    health = [r["health_score"] for r in successes if r.get("health_score") is not None]
    adapt = [r["adaptation_gain_after_loss"] for r in successes if r.get("adaptation_gain_after_loss") is not None]
    pass_rate = [r["pass_rate"] for r in successes if r.get("pass_rate") is not None]
    rounds = [r["rounds_completed"] for r in successes if r.get("rounds_completed") is not None]
    winners = [r["winner"] for r in successes if r.get("winner")]

    winner_counts: dict[str, int] = {}
    for w in winners:
        winner_counts[w] = winner_counts.get(w, 0) + 1
    top_winner = max(winner_counts, key=winner_counts.get) if winner_counts else "N/A"
    top_winner_rate = winner_counts.get(top_winner, 0) / len(winners) if winners else 0.0

    return {
        "runs": len(records),
        "success_rate": len(successes) / len(records),
        "avg_health": mean(health) if health else None,
        "avg_adapt": mean(adapt) if adapt else None,
        "avg_pass_rate": mean(pass_rate) if pass_rate else None,
        "avg_rounds": mean(rounds) if rounds else None,
        "top_winner": top_winner,
        "top_winner_rate": top_winner_rate,
        "std_health": stdev(health) if len(health) > 1 else 0.0,
    }


def fmt(v, digits=3, pct=False) -> str:
    if v is None:
        return "N/A"
    if pct:
        return f"{v*100:.1f}%"
    return f"{v:.{digits}f}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dir_a", help="First batch directory (e.g. rookie)")
    parser.add_argument("dir_b", help="Second batch directory (e.g. veteran)")
    parser.add_argument("--label-a", default=None)
    parser.add_argument("--label-b", default=None)
    args = parser.parse_args()

    root_a = Path(args.dir_a)
    root_b = Path(args.dir_b)

    label_a = args.label_a or root_a.name
    label_b = args.label_b or root_b.name

    m_a = load_manifest(root_a)
    m_b = load_manifest(root_b)

    if not m_a:
        print(f"[ERROR] Could not load results from: {root_a}")
        return 1
    if not m_b:
        print(f"[ERROR] Could not load results from: {root_b}")
        return 1

    sa = compute_stats(m_a.get("records", []))
    sb = compute_stats(m_b.get("records", []))

    w = 18
    print(f"\n{'='*62}")
    print(f"  COMPARISON: {label_a} vs {label_b}")
    print(f"{'='*62}")
    print(f"  {'Metric':<24} {label_a:>{w}} {label_b:>{w}}")
    print(f"  {'-'*58}")

    def row(label, ka, kb, pct=False, better="high"):
        va, vb = sa.get(ka), sb.get(kb or ka)
        a_str = fmt(va, pct=pct)
        b_str = fmt(vb, pct=pct)
        # Mark winner
        mark_a = mark_b = ""
        if va is not None and vb is not None:
            if better == "high":
                if va > vb + 0.001:   mark_a = " ✓"
                elif vb > va + 0.001: mark_b = " ✓"
            else:
                if va < vb - 0.001:   mark_a = " ✓"
                elif vb < va - 0.001: mark_b = " ✓"
        print(f"  {label:<24} {a_str+mark_a:>{w}} {b_str+mark_b:>{w}}")

    row("Runs",             "runs",           "runs")
    row("Success Rate",     "success_rate",   "success_rate",   pct=True)
    row("Avg Health Score", "avg_health",     "avg_health")
    row("Avg Adapt Gain",   "avg_adapt",      "avg_adapt")
    row("Avg Pass Rate",    "avg_pass_rate",  "avg_pass_rate",  pct=True, better="low")
    row("Avg Rounds Done",  "avg_rounds",     "avg_rounds")
    row("Health Std Dev",   "std_health",     "std_health",     better="low")
    print(f"  {'Top Winner':<24} {(sa.get('top_winner','?')+' '+fmt(sa.get('top_winner_rate'), pct=True)):>{w}} {(sb.get('top_winner','?')+' '+fmt(sb.get('top_winner_rate'), pct=True)):>{w}}")
    print(f"{'='*62}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
