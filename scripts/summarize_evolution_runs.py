#!/usr/bin/env python3
"""Summarize evolution campaign reports into ranked JSON/Markdown outputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_report(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _collect_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in paths:
        report = _load_report(p)
        if not report:
            continue
        best = report.get("best_candidate", {}) or {}
        rows.append(
            {
                "run_id": report.get("run_id"),
                "campaign_dir": report.get("campaign_dir"),
                "model_id": report.get("model_id"),
                "judge_model": report.get("judge_model"),
                "generations": report.get("generations"),
                "population_size": report.get("population_size"),
                "seeds": report.get("seeds"),
                "fitness": float(best.get("fitness", -999.0)),
                "aggregate_score": float(best.get("aggregate_score", 0.0)),
                "win_rate_vs_incumbent": float(best.get("win_rate_vs_incumbent", 0.0)),
                "best_candidate_id": best.get("candidate_id"),
                "best_candidate_config": report.get("best_candidate_config"),
                "report_path": str(p),
            }
        )
    rows.sort(key=lambda x: (x["fitness"], x["aggregate_score"]), reverse=True)
    return rows


def _to_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| rank | run_id | fitness | aggregate | win_rate | generations | population | seeds | candidate |",
        "|---:|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for i, r in enumerate(rows, start=1):
        seeds = ",".join(str(s) for s in (r.get("seeds") or []))
        lines.append(
            f"| {i} | {r.get('run_id')} | {r.get('fitness'):.4f} | {r.get('aggregate_score'):.4f} | "
            f"{r.get('win_rate_vs_incumbent'):.3f} | {r.get('generations')} | {r.get('population_size')} | "
            f"{seeds} | {r.get('best_candidate_id')} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Summarize evolution campaign runs")
    p.add_argument("--glob", default="logs/evolution_campaign_*/campaign_report.json")
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--output-json", default="logs/evolution_campaign_summary.json")
    p.add_argument("--output-md", default="logs/evolution_campaign_summary.md")
    args = p.parse_args()

    paths = sorted(Path(".").glob(args.glob))
    rows = _collect_rows(paths)
    top_rows = rows[: max(1, int(args.top))]

    payload = {
        "glob": args.glob,
        "count_total": len(rows),
        "count_returned": len(top_rows),
        "runs": top_rows,
    }
    out_json = Path(args.output_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    out_md = Path(args.output_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_to_markdown(top_rows), encoding="utf-8")

    print(f"Saved: {out_json}")
    print(f"Saved: {out_md}")
    if top_rows:
        best = top_rows[0]
        print(
            "Best: "
            f"run_id={best.get('run_id')} "
            f"fitness={best.get('fitness'):.4f} "
            f"aggregate={best.get('aggregate_score'):.4f} "
            f"config={best.get('best_candidate_config')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
