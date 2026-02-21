#!/usr/bin/env python3
"""Run fixed-case judge calibration and emit a JSON report."""
import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.analysis import evaluate_judge_calibration
from src.models.judge import LLMJudge, JudgeConfig
from src.runtime import normalize_model_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Judge calibration stress test")
    parser.add_argument("--model", default="stub")
    parser.add_argument("--min-pass-rate", type=float, default=0.67)
    parser.add_argument("--allow-stub", action="store_true")
    parser.add_argument("--output", default="logs/judge_calibration_report.json")
    args = parser.parse_args()

    resolved = "stub" if args.model == "stub" else normalize_model_path(args.model)
    if resolved == "stub" and not args.allow_stub:
        print("Refusing to run stub calibration without --allow-stub")
        return 1

    judge = LLMJudge(
        JudgeConfig(
            model_path=resolved,
            name="CalibrationJudge",
            randomize_argument_order=False,
            strict_runtime=not args.allow_stub,
        )
    )

    judge.load_model()
    try:
        report = evaluate_judge_calibration(judge, pass_threshold=args.min_pass_rate)
    finally:
        judge.unload_model()

    data = report.to_dict()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")

    print(
        f"Calibration pass={report.passed} "
        f"pass_rate={report.pass_rate:.3f} "
        f"threshold={report.pass_threshold:.3f}"
    )
    print(f"Saved report: {output}")
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
