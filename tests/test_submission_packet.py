#!/usr/bin/env python3
"""Tests submission packet assembly and validation."""
from pathlib import Path
import json
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark.submission_packet import build_submission_packet  # noqa: E402


def _make_summary(tmp_dir: Path) -> Path:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    trace_path = tmp_dir / "seed_101_trace.jsonl"
    trace_path.write_text('{"trace_id":"r1"}\n', encoding="utf-8")
    results_path = tmp_dir / "seed_101_results.json"
    results_path.write_text("{}", encoding="utf-8")
    registry_path = tmp_dir / "champion_registry.json"
    registry_path.write_text('{"champions":[]}', encoding="utf-8")

    summary = {
        "model_name": "stub",
        "judge_name": "stub",
        "pass_fail": "pass",
        "final_pass": True,
        "valid_run": True,
        "gate_summary": {"gates_pass": True, "validity_pass": True, "benchmark_score_pass": True},
        "score_provenance": {
            "aggregate_score_source": "model_derived",
            "model_derived_metrics_enabled": True,
            "counterfactual": {
                "primary_lane": "model_derived",
                "uplift_model_minus_fixture": {
                    "mean": 0.04,
                    "ci95_low": 0.01,
                    "ci95_high": 0.07,
                    "positive_ci95": True,
                },
            },
        },
        "artifact_paths": {"champion_registry": str(registry_path)},
        "run_metadata": {"run_label": "packet_test"},
        "seed_results": [
            {
                "seed": 101,
                "artifact_paths": {
                    "trace_jsonl": str(trace_path),
                    "results_json": str(results_path),
                },
            }
        ],
    }
    summary_path = tmp_dir / "benchmark_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary_path


def test_build_submission_packet_success() -> None:
    base = Path("logs/test_tmp_submission_packet")
    summary_path = _make_summary(base / "input")
    out_dir = base / "out"
    result = build_submission_packet(str(summary_path), output_dir=str(out_dir), run_label="manual_label")

    assert Path(result["packet_root"]).exists()
    assert Path(result["manifest_path"]).exists()
    assert Path(result["claim_memo_path"]).exists()
    assert Path(result["summary_path"]).exists()
    assert result["file_count"] >= 3

    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    kinds = {entry["kind"] for entry in manifest["files"]}
    assert "summary" in kinds
    assert "claim_memo" in kinds
    assert "seed_artifact:trace_jsonl" in kinds


def test_build_submission_packet_rejects_missing_provenance() -> None:
    base = Path("logs/test_tmp_submission_packet_invalid")
    summary_path = _make_summary(base / "input")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary.pop("score_provenance", None)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    try:
        build_submission_packet(str(summary_path), output_dir=str(base / "out"))
        assert False, "Expected ValueError for missing score_provenance"
    except ValueError as exc:
        assert "score_provenance" in str(exc)


if __name__ == "__main__":
    test_build_submission_packet_success()
    test_build_submission_packet_rejects_missing_provenance()
    print("test_submission_packet: PASS")
