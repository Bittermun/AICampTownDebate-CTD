"""Helpers for phase-1 benchmark batch orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json


@dataclass
class BatchRunRecord:
    run_id: str
    attempt: int
    seed: int
    topic_set: str
    summary_path: str
    registry_path: str
    return_code: int
    bankrupt: bool
    terminal_bankrupt: bool
    pass_fail: str = "unknown"
    final_pass: bool = False
    benchmark_score_pass: bool = False
    gates_pass: bool = False
    validity_pass: bool = False
    degraded_mode: bool = False
    live_source_failures: int = 0
    original_model_id: str = ""
    effective_model_id: str = ""
    was_replaced: bool = False
    replacement_index: int = 0
    replaced_from_run_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "attempt": self.attempt,
            "seed": self.seed,
            "topic_set": self.topic_set,
            "summary_path": self.summary_path,
            "registry_path": self.registry_path,
            "return_code": self.return_code,
            "bankrupt": self.bankrupt,
            "terminal_bankrupt": self.terminal_bankrupt,
            "pass_fail": self.pass_fail,
            "final_pass": self.final_pass,
            "benchmark_score_pass": self.benchmark_score_pass,
            "gates_pass": self.gates_pass,
            "validity_pass": self.validity_pass,
            "degraded_mode": self.degraded_mode,
            "live_source_failures": self.live_source_failures,
            "original_model_id": self.original_model_id,
            "effective_model_id": self.effective_model_id,
            "was_replaced": self.was_replaced,
            "replacement_index": self.replacement_index,
            "replaced_from_run_id": self.replaced_from_run_id,
        }


def load_json(path: str) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def detect_bankruptcy_from_summary(summary_payload: Dict[str, Any]) -> bool:
    for seed in summary_payload.get("seed_results", []):
        artifact_paths = seed.get("artifact_paths", {})
        result_path = artifact_paths.get("results_json")
        if not result_path:
            continue
        p = Path(result_path)
        if not p.exists():
            continue
        try:
            result_payload = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        balances = result_payload.get("final_balances", {})
        if any(float(v) <= 0.0 for v in balances.values()):
            return True
    return False


def should_retry_bankruptcy(bankrupt: bool, attempt: int, max_retries: int) -> bool:
    return bankrupt and attempt <= max_retries


def summarize_batch(records: Iterable[BatchRunRecord]) -> Dict[str, Any]:
    rows = list(records)
    if not rows:
        return {
            "runs": 0,
            "final_pass_rate": 0.0,
            "benchmark_score_pass_rate": 0.0,
            "gates_pass_rate": 0.0,
            "validity_pass_rate": 0.0,
            "bankruptcy_rate": 0.0,
            "degraded_mode_rate": 0.0,
            "live_source_failure_runs": 0,
            "replacement_run_count": 0,
            "replacement_success_rate": 0.0,
        }

    n = len(rows)
    def _rate(pred) -> float:
        return round(sum(1 for r in rows if pred(r)) / n, 6)

    replacement_rows = [r for r in rows if r.was_replaced]
    replacement_count = len(replacement_rows)

    return {
        "runs": n,
        "final_pass_rate": _rate(lambda r: r.final_pass),
        "benchmark_score_pass_rate": _rate(lambda r: r.benchmark_score_pass),
        "gates_pass_rate": _rate(lambda r: r.gates_pass),
        "validity_pass_rate": _rate(lambda r: r.validity_pass),
        "bankruptcy_rate": _rate(lambda r: r.terminal_bankrupt),
        "degraded_mode_rate": _rate(lambda r: r.degraded_mode),
        "live_source_failure_runs": sum(1 for r in rows if r.live_source_failures > 0),
        "replacement_run_count": replacement_count,
        "replacement_success_rate": round(
            sum(1 for r in replacement_rows if r.final_pass) / replacement_count, 6
        )
        if replacement_count > 0
        else 0.0,
    }


def persist_jsonl(path: str, payloads: Iterable[Dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for row in payloads:
            f.write(json.dumps(row, sort_keys=True) + "\n")
