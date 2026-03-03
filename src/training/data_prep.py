"""Build training-ready datasets from benchmark summary trace artifacts."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import json

from .contracts import (
    PreferencePair,
    SFTExample,
    build_preference_pairs_from_rounds,
    build_sft_examples_from_traces,
    make_manifest,
    save_manifest,
)

_TIER_ORDER = {"tier_c": 1, "tier_b": 2, "tier_a": 3}


@dataclass
class TrainingDataBuildResult:
    output_dir: str
    summary_path: str
    run_ids: List[str]
    trace_paths: List[str]
    trace_count_input: int
    trace_count_selected: int
    sft_count: int
    preference_count: int
    sft_path: str
    preference_path: str
    manifest_path: str
    report_path: str
    filters: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def _load_json(path: str) -> Dict[str, Any]:
    p = Path(path)
    _require(p.exists(), f"Summary JSON not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    _require(p.exists(), f"Trace JSONL not found: {p}")
    rows: List[Dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _write_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(r, sort_keys=True) for r in rows)
    if payload:
        payload += "\n"
    p.write_text(payload, encoding="utf-8")


def _tier_threshold(min_tier: str) -> int:
    key = min_tier.strip().lower()
    _require(key in _TIER_ORDER, f"Unsupported min_tier: {min_tier}")
    return _TIER_ORDER[key]


def _normalize_tier_set(include_tiers: Optional[List[str]]) -> Optional[Set[str]]:
    if not include_tiers:
        return None
    normalized = {x.strip().lower() for x in include_tiers if x.strip()}
    invalid = sorted([x for x in normalized if x not in _TIER_ORDER])
    _require(len(invalid) == 0, f"Unsupported tier(s): {', '.join(invalid)}")
    return normalized


def _select_traces(
    traces: List[Dict[str, Any]],
    *,
    min_tier: str,
    include_tiers: Optional[List[str]],
) -> List[Dict[str, Any]]:
    min_rank = _tier_threshold(min_tier)
    include = _normalize_tier_set(include_tiers)
    selected: List[Dict[str, Any]] = []
    for row in traces:
        tier = str(row.get("judge_reliability_tier", "tier_c")).lower()
        rank = _TIER_ORDER.get(tier, 0)
        if rank < min_rank:
            continue
        if include is not None and tier not in include:
            continue
        selected.append(row)
    return selected


def build_training_data_from_summary(
    summary_path: str,
    *,
    output_dir: str,
    min_tier: str = "tier_b",
    include_tiers: Optional[List[str]] = None,
    notes: str = "",
) -> TrainingDataBuildResult:
    """
    Build SFT/preference datasets from benchmark summary + per-seed trace JSONL.
    """
    summary = _load_json(summary_path)
    seed_results = summary.get("seed_results", [])
    _require(isinstance(seed_results, list) and len(seed_results) > 0, "seed_results missing from summary")

    trace_paths: List[str] = []
    all_traces: List[Dict[str, Any]] = []
    for seed_result in seed_results:
        artifacts = seed_result.get("artifact_paths", {}) or {}
        trace_path = artifacts.get("trace_jsonl")
        _require(trace_path is not None, "seed artifact_paths missing trace_jsonl")
        trace_paths.append(str(trace_path))
        rows = _load_jsonl(str(trace_path))
        all_traces.extend(rows)

    selected = _select_traces(all_traces, min_tier=min_tier, include_tiers=include_tiers)
    _require(len(selected) > 0, "No traces passed filtering; relax min_tier/include_tiers")

    sft_examples = build_sft_examples_from_traces(selected)
    preference_pairs = build_preference_pairs_from_rounds(summary=summary, traces=selected)

    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    sft_path = out_root / "sft_examples.jsonl"
    pref_path = out_root / "preference_pairs.jsonl"
    manifest_path = out_root / "training_dataset_manifest.json"
    report_path = out_root / "training_data_report.json"

    _write_jsonl(str(sft_path), [x.to_dict() if isinstance(x, SFTExample) else x for x in sft_examples])
    _write_jsonl(
        str(pref_path),
        [x.to_dict() if isinstance(x, PreferencePair) else x for x in preference_pairs],
    )

    run_id = str(summary.get("run_metadata", {}).get("run_id", "")).strip()
    run_ids = [run_id] if run_id else []
    manifest = make_manifest(
        run_ids=run_ids,
        trace_paths=trace_paths,
        sft_path=str(sft_path),
        preference_path=str(pref_path),
        filters={
            "min_tier": min_tier,
            "include_tiers": include_tiers or [],
        },
        notes=notes,
    )
    save_manifest(manifest, str(manifest_path))

    report = TrainingDataBuildResult(
        output_dir=str(out_root),
        summary_path=str(summary_path),
        run_ids=run_ids,
        trace_paths=trace_paths,
        trace_count_input=len(all_traces),
        trace_count_selected=len(selected),
        sft_count=len(sft_examples),
        preference_count=len(preference_pairs),
        sft_path=str(sft_path),
        preference_path=str(pref_path),
        manifest_path=str(manifest_path),
        report_path=str(report_path),
        filters={"min_tier": min_tier, "include_tiers": include_tiers or []},
    )
    report_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return report
