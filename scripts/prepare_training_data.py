#!/usr/bin/env python3
"""Prepare SFT/preference datasets from benchmark trace artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.training import build_training_data_from_summary  # noqa: E402


def _parse_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build training datasets from benchmark summary trace artifacts")
    parser.add_argument("--summary", required=True, help="Path to benchmark summary JSON")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: logs/training_data_<timestamp>)",
    )
    parser.add_argument(
        "--min-tier",
        default="tier_b",
        choices=["tier_a", "tier_b", "tier_c"],
        help="Minimum judge reliability tier to include",
    )
    parser.add_argument(
        "--include-tiers",
        default="",
        help="Optional comma list to explicitly include (e.g. tier_a,tier_b)",
    )
    parser.add_argument("--notes", default="", help="Optional manifest notes")
    args = parser.parse_args()

    if args.output_dir:
        out_dir = args.output_dir
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = str(Path("logs") / f"training_data_{ts}")

    include_tiers = _parse_csv(args.include_tiers)
    try:
        result = build_training_data_from_summary(
            summary_path=args.summary,
            output_dir=out_dir,
            min_tier=args.min_tier,
            include_tiers=include_tiers,
            notes=args.notes,
        )
    except Exception as exc:
        print(f"[ERROR] failed to build training data: {exc}")
        return 2

    payload = result.to_dict()
    print(json.dumps(payload, indent=2))
    print(f"[training] sft={payload['sft_count']} preference={payload['preference_count']}")
    print(f"[training] manifest={payload['manifest_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
