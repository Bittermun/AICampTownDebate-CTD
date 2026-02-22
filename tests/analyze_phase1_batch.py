#!/usr/bin/env python3
"""Aggregate a batch summary JSONL file into a compact report."""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark.batch_utils import BatchRunRecord, summarize_batch  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Aggregate phase-1 batch JSONL")
    p.add_argument("--summary-jsonl", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()

    records = []
    for line in Path(args.summary_jsonl).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        records.append(BatchRunRecord(**raw))

    agg = summarize_batch(records)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(agg, indent=2), encoding="utf-8")
    print(f"Saved aggregate report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

