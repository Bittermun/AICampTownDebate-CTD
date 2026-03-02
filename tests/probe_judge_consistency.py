#!/usr/bin/env python3
"""
Judge Consistency Probe

Loads the most recent tournament transcript, extracts the opening arguments from
the first round, and runs them through the judge N times to measure score variance.

Usage:
    python tests/probe_judge_consistency.py
    python tests/probe_judge_consistency.py --transcript logs/last_run_transcript.json
    python tests/probe_judge_consistency.py --runs 10 --model qwen2.5:7b
"""
import sys
import json
import argparse
import statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.judge import LLMJudge, JudgeConfig
from src.runtime import normalize_model_path


def load_arguments_from_transcript(path: str):
    """Extract the first round's opening arguments from a transcript JSON."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rounds = data.get("rounds", [])
    if not rounds:
        print(f"[ERROR] No rounds found in {path}")
        sys.exit(1)

    first_round = rounds[0]
    turns = first_round.get("turns", [])

    # Find argument turns (type="argument")
    arg_turns = [t for t in turns if t.get("type") == "argument"]
    if len(arg_turns) < 2:
        print(f"[ERROR] Need at least 2 argument turns, found {len(arg_turns)}")
        sys.exit(1)

    topic = first_round.get("topic", "Unknown topic")
    arg_a = arg_turns[0].get("content", "")
    arg_b = arg_turns[1].get("content", "")

    return topic, arg_a, arg_b


def run_probe(transcript_path: str, model: str, runs: int, max_stdev: float):
    topic, arg_a, arg_b = load_arguments_from_transcript(transcript_path)

    print(f"\n{'='*60}")
    print("JUDGE CONSISTENCY PROBE")
    print(f"{'='*60}")
    print(f"Transcript: {Path(transcript_path).name}")
    print(f"Model:      {model}")
    print(f"Runs:       {runs}")
    print(f"Topic:      {topic[:70]}...")
    print(f"Arg A:      {len(arg_a.split())} words | Arg B: {len(arg_b.split())} words")
    print(f"{'='*60}\n")

    judge = LLMJudge(JudgeConfig(
        model_path=normalize_model_path(model),
        name="ProbeJudge",
        randomize_argument_order=False,   # Fixed order for reproducibility
        ensemble_judge=False,             # Single eval per run to measure raw variance
        strict_runtime=False,
    ))
    judge.load_model()

    confidences_a = []
    try:
        for i in range(runs):
            j = judge.evaluate(
                topic=topic,
                argument_a=arg_a,
                argument_b=arg_b,
                round_id=i + 1,
            )
            confidences_a.append(j.confidence_a)
            print(f"  Run {i+1:2d}: A={j.confidence_a:.4f}  B={j.confidence_b:.4f}  | {j.reasoning[:80]}")
    finally:
        judge.unload_model()

    mean_a = statistics.mean(confidences_a)
    stdev_a = statistics.stdev(confidences_a) if len(confidences_a) > 1 else 0.0
    spread = max(confidences_a) - min(confidences_a)
    variance_pass = stdev_a <= max_stdev

    print(f"\n{'─'*60}")
    print(f"  Mean A:  {mean_a:.4f}")
    print(f"  StdDev:  {stdev_a:.4f}  (threshold: {max_stdev})")
    print(f"  Range:   {spread:.4f}  (max - min)")
    print(f"  Result:  {'✓ PASS — signal is stable' if variance_pass else '✗ FAIL — signal too noisy'}")

    # Signal quality interpretation
    if stdev_a < 0.03:
        quality = "EXCELLENT — judge is highly deterministic"
    elif stdev_a < 0.06:
        quality = "GOOD — acceptable for economic signal"
    elif stdev_a < 0.12:
        quality = "MARGINAL — consider ensemble_judge=True to reduce noise"
    else:
        quality = "POOR — economic signal is not trustworthy at this variance"

    print(f"  Quality: {quality}")
    print(f"{'─'*60}\n")

    return {
        "mean_a": round(mean_a, 4),
        "stdev_a": round(stdev_a, 4),
        "spread": round(spread, 4),
        "runs": runs,
        "variance_pass": variance_pass,
        "model": model,
    }


def main():
    parser = argparse.ArgumentParser(description="Judge consistency probe")
    parser.add_argument(
        "--transcript",
        default="logs/last_run_transcript.json",
        help="Path to transcript JSON (default: logs/last_run_transcript.json)",
    )
    parser.add_argument("--model", default="qwen2.5:1.5b", help="Model to probe")
    parser.add_argument("--runs", type=int, default=7, help="Number of judge runs")
    parser.add_argument("--max-stdev", type=float, default=0.06, help="Max acceptable stdev")
    args = parser.parse_args()

    transcript = args.transcript
    if not Path(transcript).exists():
        # Try tournament_results_transcript.json as fallback
        fallback = "logs/tournament_results_transcript.json"
        if Path(fallback).exists():
            transcript = fallback
            print(f"[INFO] Using fallback transcript: {fallback}")
        else:
            print(f"[ERROR] No transcript found at {args.transcript}")
            sys.exit(1)

    result = run_probe(transcript, args.model, args.runs, args.max_stdev)

    # Save report
    out_path = Path("logs/judge_consistency_report.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Report saved to {out_path}")


if __name__ == "__main__":
    main()
