"""Champion registry and ELO/tier update logic."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Dict, List, Tuple
import hashlib
import json

from .config_models import BenchmarkPolicy, TierBand


def _tier_from_elo(elo: float, tiers: List[TierBand]) -> str:
    for t in tiers:
        if t.min_elo <= elo <= t.max_elo:
            return t.name
    return "Unranked"


def load_registry(path: str) -> Dict:
    p = Path(path)
    if not p.exists():
        return {"models": {}, "history": []}
    return json.loads(p.read_text(encoding="utf-8"))


def save_registry(path: str, data: Dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(p)


def _stable_hash(obj: Dict) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def update_registry_if_eligible(
    registry: Dict,
    policy: BenchmarkPolicy,
    model_name: str,
    judge_name: str,
    aggregate_score: float,
    valid_run: bool,
    passed: bool,
    metadata: Dict,
) -> Tuple[Dict, Dict[str, float], Dict[str, str], List[str]]:
    """Update model ranking only when valid+passed by policy."""
    notes: List[str] = []
    models = registry.setdefault("models", {})
    elo_policy = policy.league.elo

    if model_name not in models:
        models[model_name] = {
            "performer_id": metadata.get("performer_id"),
            "parent_performer_id": metadata.get("parent_performer_id"),
            "variant_label": metadata.get("variant_label"),
            "elo": float(elo_policy.initial_rating),
            "matches": 0,
            "tier": _tier_from_elo(float(elo_policy.initial_rating), policy.league.tiers),
            "frozen": False,
            "windows": [],
            "manifest": {},
            "judge_name": judge_name,
        }

    entry = models[model_name]
    if metadata.get("performer_id"):
        entry["performer_id"] = metadata.get("performer_id")
    if metadata.get("parent_performer_id"):
        entry["parent_performer_id"] = metadata.get("parent_performer_id")
    if metadata.get("variant_label"):
        entry["variant_label"] = metadata.get("variant_label")
    elo_before = float(entry["elo"])
    tier_before = str(entry.get("tier", "Unranked"))

    if not policy.league.enabled:
        notes.append("League disabled; registry unchanged.")
        return registry, {"before": elo_before, "after": elo_before}, {"before": tier_before, "after": tier_before}, notes

    if not (valid_run and passed):
        notes.append("Registry not updated (requires valid_run && passed).")
        return registry, {"before": elo_before, "after": elo_before}, {"before": tier_before, "after": tier_before}, notes

    matches = int(entry.get("matches", 0))
    k = elo_policy.k_factor.k_provisional if matches < elo_policy.k_factor.provisional_matches else elo_policy.k_factor.k_stable
    expected = 0.5
    actual = max(0.0, min(1.0, aggregate_score))
    elo_after = elo_before + (k * (actual - expected))
    entry["elo"] = round(elo_after, 3)
    entry["matches"] = matches + 1
    entry["tier"] = _tier_from_elo(entry["elo"], policy.league.tiers)
    entry["judge_name"] = judge_name

    window = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "run_id": metadata.get("run_id"),
        "performer_id": entry.get("performer_id"),
        "parent_performer_id": entry.get("parent_performer_id"),
        "variant_label": entry.get("variant_label"),
        "aggregate_score": aggregate_score,
        "valid_run": valid_run,
        "passed": passed,
        "metadata_hash": _stable_hash(metadata),
    }
    entry.setdefault("windows", []).append(window)

    if policy.champion_freeze.enabled:
        _maybe_freeze(entry, policy, metadata, notes)

    registry.setdefault("history", []).append(
        {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "model": model_name,
            "performer_id": entry.get("performer_id"),
            "parent_performer_id": entry.get("parent_performer_id"),
            "variant_label": entry.get("variant_label"),
            "run_id": metadata.get("run_id"),
            "elo_before": elo_before,
            "elo_after": entry["elo"],
            "tier_before": tier_before,
            "tier_after": entry["tier"],
            "aggregate_score": aggregate_score,
            "valid_run": valid_run,
            "passed": passed,
        }
    )

    return registry, {"before": elo_before, "after": float(entry["elo"])}, {"before": tier_before, "after": str(entry["tier"])}, notes


def _maybe_freeze(entry: Dict, policy: BenchmarkPolicy, metadata: Dict, notes: List[str]) -> None:
    req = policy.champion_freeze.freeze_requirements
    windows = entry.get("windows", [])
    if len(windows) < req.min_windows:
        return

    recent = windows[-req.min_windows :]
    if req.require_all_gates_passed_each_window and not all(w.get("valid_run", False) for w in recent):
        return
    if req.require_benchmark_pass_each_window and not all(w.get("passed", False) for w in recent):
        return

    entry["frozen"] = True
    manifest = {
        "frozen_at": datetime.utcnow().isoformat() + "Z",
        "mean_recent_aggregate": round(float(mean([float(w["aggregate_score"]) for w in recent])), 6),
        "model_identifier": metadata.get("model_identifier", metadata.get("model_name", "unknown")),
        "model_version_or_hash": metadata.get("model_version_or_hash", _stable_hash(metadata)),
        "system_prompt_hash": metadata.get("system_prompt_hash", "unknown"),
        "config_hash": metadata.get("config_hash", "unknown"),
        "judge_config_hash": metadata.get("judge_config_hash", "unknown"),
        "tooling_version": metadata.get("tooling_version", "phase1"),
        "seed_set": metadata.get("seed_set", []),
        "artifact_paths": metadata.get("artifact_paths", {}),
    }
    entry["manifest"] = manifest
    notes.append("Model freeze activated (requirements satisfied).")
