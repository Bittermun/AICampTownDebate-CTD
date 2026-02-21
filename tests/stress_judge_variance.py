#!/usr/bin/env python3
"""Stress test: judge variance and synthesis behavior."""
import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.judge import JudgeConfig, LLMJudge
from src.analysis.judge_variance import evaluate_judge_variance


DEFAULT_TOPIC = "Should humans colonize Mars?"
DEFAULT_ARGUMENT_A = (
    "While my opponent correctly points out the immense radiation risks of Mars, "
    "this strengthens the need to begin now. We must solve shielding challenges "
    "to become a multi-planetary species."
)
DEFAULT_ARGUMENT_B = (
    "Colonizing Mars is too expensive. We should spend the money on Earth. "
    "Mars is a barren wasteland and we have no business being there."
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Judge variance stress test")
    parser.add_argument("--model", default="ollama:qwen2.5:1.5b", help="Judge model path")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--max-stdev", type=float, default=0.05)
    parser.add_argument("--min-mean-a", type=float, default=0.55)
    parser.add_argument("--output", default="logs/judge_variance.json", help="Optional JSON report path")
    args = parser.parse_args()

    print("=== STRESS TEST: Judge Variance ===")
    print(f"Model: {args.model}")
    print(f"Runs: {args.runs} | Max StdDev: {args.max_stdev:.3f} | Min Mean A: {args.min_mean_a:.3f}")

    judge = LLMJudge(JudgeConfig(model_path=args.model, name="VarianceTestJudge"))
    judge.load_model()

    try:
        result = evaluate_judge_variance(
            judge=judge,
            topic=DEFAULT_TOPIC,
            argument_a=DEFAULT_ARGUMENT_A,
            argument_b=DEFAULT_ARGUMENT_B,
            runs=args.runs,
            max_stdev=args.max_stdev,
            min_mean_a=args.min_mean_a,
            round_id=2,
        )
    finally:
        judge.unload_model()

    print("\n=== RESULTS ===")
    print(f"Mean Confidence A: {result.mean_confidence_a:.3f}")
    print(f"StdDev Confidence A: {result.stdev_confidence_a:.3f}")
    print(f"Synthesis pass: {result.synthesis_pass}")
    print(f"Variance pass: {result.variance_pass}")
    print(f"Overall pass: {result.passed}")

    report = {
        "model": args.model,
        "topic": DEFAULT_TOPIC,
        **result.to_dict(),
        "thresholds": {
            "max_stdev": args.max_stdev,
            "min_mean_a": args.min_mean_a,
        },
    }

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Saved report: {out_path}")

    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
