#!/usr/bin/env python3
"""Run phase-1 benchmark policy and emit summary + registry artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark import load_benchmark_policy, run_phase1
from src.benchmark.registry import load_registry, save_registry, update_registry_if_eligible


def _parse_seeds(raw: str | None, default: list[int]) -> list[int]:
    if not raw:
        return default
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 1 benchmark orchestrator")
    parser.add_argument("--config", default="configs/benchmark_phase1.yaml")
    parser.add_argument("--tournament-config", default="configs/vllm_tournament_recommended.yaml")
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--seeds", default=None, help="Comma-separated override, e.g. 101,202,303")
    parser.add_argument("--offline-fixtures-dir", default="benchmarks/fixtures")
    parser.add_argument("--output-summary", default=None)
    parser.add_argument("--output-registry", default=None)
    parser.add_argument("--num-rounds-override", type=int, default=None)
    parser.add_argument("--max-iterations-override", type=int, default=None)
    parser.add_argument("--parent-performer-id", default=None)
    parser.add_argument("--variant-label", default=None)
    parser.add_argument("--allow-stub", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    policy = load_benchmark_policy(args.config)
    seeds = _parse_seeds(args.seeds, policy.meta.seed_policy.seeds)

    summary_path = args.output_summary or policy.reporting.output_paths.benchmark_summary
    registry_path = args.output_registry or policy.reporting.output_paths.champion_registry

    try:
        result = run_phase1(
            policy=policy,
            tournament_config_path=args.tournament_config,
            model_name=args.model_id,
            judge_model_override=args.judge_model,
            seeds=seeds,
            fixtures_dir=args.offline_fixtures_dir,
            allow_stub=args.allow_stub,
            dry_run=args.dry_run,
            num_rounds_override=args.num_rounds_override,
            max_iterations_override=args.max_iterations_override,
            parent_performer_id=args.parent_performer_id,
            variant_label=args.variant_label,
        )
    except Exception as e:
        print(f"[ERROR] benchmark run failed: {e}")
        return 4

    metadata = {
        "model_name": result.model_name,
        "judge_name": result.judge_name,
        "model_identifier": args.model_id,
        "model_version_or_hash": args.model_id,
        "system_prompt_hash": "unknown",
        "config_hash": args.config,
        "judge_config_hash": args.judge_model or "from_tournament_config",
        "tooling_version": "phase1_live_hf_v1",
        "seed_set": seeds,
        "artifact_paths": result.artifact_paths,
        "run_id": result.run_metadata.get("run_id"),
        "performer_id": result.run_metadata.get("performer_id"),
        "parent_performer_id": result.run_metadata.get("parent_performer_id"),
        "variant_label": result.run_metadata.get("variant_label"),
        "prompt_hashes": result.run_metadata.get("prompt_hashes", {}),
        "runtime_fingerprint": result.run_metadata.get("runtime_fingerprint", {}),
        "artifact_manifest": result.run_metadata.get("artifact_manifest", {}),
        "live_sources_used": result.live_sources_used,
        "live_source_failures": result.live_source_failures,
        "degraded_mode_reason": result.degraded_mode_reason,
    }

    registry = load_registry(registry_path)
    updated_registry, elo_change, tier_change, reg_notes = update_registry_if_eligible(
        registry=registry,
        policy=policy,
        model_name=result.model_name,
        judge_name=result.judge_name,
        aggregate_score=result.aggregate_score,
        valid_run=result.valid_run,
        passed=result.final_pass,
        metadata=metadata,
    )
    save_registry(registry_path, updated_registry)

    result.elo_before_after = elo_change
    result.tier_before_after = tier_change
    result.notes.extend(reg_notes)
    result.artifact_paths["champion_registry"] = registry_path
    result.artifact_paths["results_json"] = summary_path
    payload = result.to_dict()
    missing_fields = [f for f in policy.reporting.required_summary_fields if f not in payload]
    if missing_fields:
        print(f"[ERROR] required summary fields missing: {missing_fields}")
        return 4

    out = Path(summary_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    payload["run_metadata"]["artifact_manifest"] = payload["run_metadata"].get("artifact_manifest", {})
    payload["run_metadata"]["artifact_manifest"]["registry_json"] = {
        "path": registry_path,
        "sha256": _sha256_file(registry_path),
    }
    payload["run_metadata"]["artifact_manifest"]["summary_json"] = {
        "path": summary_path,
        "sha256": _sha256_file(str(out)),
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Saved benchmark summary: {out}")
    print(f"Saved champion registry: {registry_path}")
    print(
        f"Result: pass_fail={result.pass_fail} valid_run={result.valid_run} "
        f"aggregate_score={result.aggregate_score:.3f}"
    )

    if not result.valid_run:
        return 3
    if result.final_pass:
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
