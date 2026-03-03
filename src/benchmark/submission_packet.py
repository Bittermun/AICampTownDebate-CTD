"""Submission packet builder for benchmark claim artifacts."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json
import shutil


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def _load_summary(path: str) -> Dict[str, Any]:
    p = Path(path)
    _require(p.exists(), f"Summary JSON not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _validate_summary(summary: Dict[str, Any]) -> None:
    _require("score_provenance" in summary, "Missing score_provenance in benchmark summary")
    provenance = summary.get("score_provenance", {})
    _require(isinstance(provenance, dict), "score_provenance must be an object")
    _require("counterfactual" in provenance, "Missing score_provenance.counterfactual")
    counterfactual = provenance.get("counterfactual", {})
    _require(
        isinstance(counterfactual, dict) and "uplift_model_minus_fixture" in counterfactual,
        "Missing score_provenance.counterfactual.uplift_model_minus_fixture",
    )
    seed_results = summary.get("seed_results", [])
    _require(isinstance(seed_results, list) and len(seed_results) > 0, "Missing seed_results in summary")
    for seed_result in seed_results:
        artifacts = seed_result.get("artifact_paths", {}) or {}
        trace_path = artifacts.get("trace_jsonl")
        _require(trace_path is not None, "Missing trace_jsonl in seed artifact_paths")
        _require(Path(trace_path).exists(), f"trace_jsonl not found: {trace_path}")


def _copy_file(src: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _build_claim_memo(summary: Dict[str, Any], run_label: Optional[str]) -> str:
    gate = summary.get("gate_summary", {})
    prov = summary.get("score_provenance", {})
    cf = prov.get("counterfactual", {})
    uplift = cf.get("uplift_model_minus_fixture", {})

    lines = [
        "# Claim Memo",
        "",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
        f"- Run label: {run_label or summary.get('run_metadata', {}).get('run_label') or 'none'}",
        f"- Model: {summary.get('model_name', 'unknown')}",
        f"- Judge: {summary.get('judge_name', 'unknown')}",
        "",
        "## Outcome",
        f"- pass_fail: `{summary.get('pass_fail', 'unknown')}`",
        f"- final_pass: `{summary.get('final_pass', False)}`",
        f"- valid_run: `{summary.get('valid_run', False)}`",
        "",
        "## Scoring Provenance",
        f"- aggregate_score_source: `{prov.get('aggregate_score_source', 'unknown')}`",
        f"- model_derived_metrics_enabled: `{prov.get('model_derived_metrics_enabled', False)}`",
        f"- counterfactual primary lane: `{cf.get('primary_lane', 'unknown')}`",
        f"- uplift mean: `{uplift.get('mean', 0.0)}`",
        f"- uplift CI95: `[{uplift.get('ci95_low', 0.0)}, {uplift.get('ci95_high', 0.0)}]`",
        f"- uplift positive_ci95: `{uplift.get('positive_ci95', False)}`",
        "",
        "## Gate Snapshot",
        f"- benchmark_score_pass: `{gate.get('benchmark_score_pass', False)}`",
        f"- gates_pass: `{gate.get('gates_pass', False)}`",
        f"- validity_pass: `{gate.get('validity_pass', False)}`",
        "",
        "## Notes",
        "- This packet is evidence-ready but does not imply a quality claim unless all required gates pass.",
    ]
    return "\n".join(lines) + "\n"


def build_submission_packet(
    summary_path: str,
    output_dir: Optional[str] = None,
    run_label: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a submission-ready packet from benchmark summary artifacts.

    Returns packet metadata with output paths and file manifest.
    """
    summary = _load_summary(summary_path)
    _validate_summary(summary)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    packet_root = Path(output_dir) if output_dir else Path("logs") / f"submission_packet_{ts}"
    packet_root.mkdir(parents=True, exist_ok=True)

    files_manifest: List[Dict[str, Any]] = []

    def _record(src: str, dst: Path, kind: str) -> None:
        _copy_file(src, dst)
        files_manifest.append(
            {
                "kind": kind,
                "src": str(Path(src)),
                "dst": str(dst),
                "sha256": _sha256_file(str(dst)),
                "bytes": dst.stat().st_size,
            }
        )

    summary_src = str(Path(summary_path))
    summary_dst = packet_root / "benchmark_summary.json"
    _record(summary_src, summary_dst, "summary")

    registry_src = str(summary.get("artifact_paths", {}).get("champion_registry", ""))
    if registry_src and Path(registry_src).exists():
        _record(registry_src, packet_root / "champion_registry.json", "registry")

    for seed_result in summary.get("seed_results", []):
        seed = seed_result.get("seed", "unknown")
        artifacts = seed_result.get("artifact_paths", {}) or {}
        seed_dir = packet_root / "seeds" / f"seed_{seed}"
        for key, src in artifacts.items():
            if not src or not Path(src).exists():
                continue
            dst = seed_dir / Path(src).name
            _record(str(src), dst, f"seed_artifact:{key}")

    claim_memo = _build_claim_memo(summary, run_label=run_label)
    claim_path = packet_root / "CLAIM_MEMO.md"
    claim_path.write_text(claim_memo, encoding="utf-8")
    files_manifest.append(
        {
            "kind": "claim_memo",
            "src": "",
            "dst": str(claim_path),
            "sha256": _sha256_file(str(claim_path)),
            "bytes": claim_path.stat().st_size,
        }
    )

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_label": run_label,
        "packet_root": str(packet_root),
        "summary_source": summary_src,
        "model_name": summary.get("model_name"),
        "judge_name": summary.get("judge_name"),
        "pass_fail": summary.get("pass_fail"),
        "final_pass": summary.get("final_pass"),
        "valid_run": summary.get("valid_run"),
        "files": files_manifest,
    }
    manifest_path = packet_root / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "packet_root": str(packet_root),
        "manifest_path": str(manifest_path),
        "claim_memo_path": str(claim_path),
        "summary_path": str(summary_dst),
        "file_count": len(files_manifest),
    }

