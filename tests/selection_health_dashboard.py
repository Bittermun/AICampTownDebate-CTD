#!/usr/bin/env python3
"""Compute Selection Health Dashboard from tournament artifacts."""
import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.analysis import compute_selection_health


def _load_json(path: str):
    p = Path(path)
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="Selection health dashboard")
    parser.add_argument("--transcript", default="logs/tournament_results_transcript.json")
    parser.add_argument("--results", default="logs/tournament_results.json")
    parser.add_argument("--ledger", default="logs/tournament_results_ledger.json")
    parser.add_argument("--output", default="logs/selection_health_dashboard.json")
    args = parser.parse_args()

    transcript = _load_json(args.transcript)
    if transcript is None:
        print(f"Transcript not found: {args.transcript}")
        return 1
    results = _load_json(args.results)
    ledger = _load_json(args.ledger)

    report = compute_selection_health(transcript=transcript, results=results, ledger=ledger)
    data = report.to_dict()

    print("Selection Health Dashboard")
    print(f"  rounds_total: {data['rounds_total']}")
    print(f"  bankruptcy_rate: {data['bankruptcy_rate']:.3f}")
    print(f"  pass_rate: {data['pass_rate']:.3f}")
    print(f"  aggression_rate: {data['aggression_rate']:.3f}")
    print(f"  mutual_pass_round_rate: {data['mutual_pass_round_rate']:.3f}")
    print(f"  avg_iterations: {data['avg_iterations']:.3f}")
    print(f"  judge_score_entropy_bits: {data['judge_score_entropy_bits']:.3f}")
    print(f"  judge_margin_mean: {data['judge_margin_mean']:.3f}")
    print(f"  adaptation_gain_after_loss: {data['adaptation_gain_after_loss']:.3f}")
    print(f"  economy_reasoning_rate: {data['economy_reasoning_rate']:.3f}")
    print(f"  health_score: {data['health_score']:.3f}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Saved dashboard: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

