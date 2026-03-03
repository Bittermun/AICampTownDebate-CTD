#!/usr/bin/env python3
"""Assemble a submission-ready artifact packet from benchmark summary JSON."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark.submission_packet import build_submission_packet  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build submission packet from benchmark summary")
    parser.add_argument("--summary", required=True, help="Path to benchmark summary JSON")
    parser.add_argument("--output-dir", default=None, help="Optional output directory for packet")
    parser.add_argument("--run-label", default=None, help="Optional run label override")
    args = parser.parse_args()

    try:
        result = build_submission_packet(
            summary_path=args.summary,
            output_dir=args.output_dir,
            run_label=args.run_label,
        )
    except Exception as exc:
        print(f"[ERROR] Failed to build submission packet: {exc}")
        return 2

    print(json.dumps(result, indent=2))
    print(f"[packet] root: {result['packet_root']}")
    print(f"[packet] manifest: {result['manifest_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

