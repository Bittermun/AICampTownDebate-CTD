"""Helpers for phase-1 benchmark batch orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import time
from typing import Any, Dict, Iterable, List, Optional
import json

CHECKPOINT_ENVELOPE_SCHEMA_KEY = "__schema__"
CHECKPOINT_ENVELOPE_VERSION_KEY = "__version__"
CHECKPOINT_ENVELOPE_RECORD_KEY = "record"
CHECKPOINT_ENVELOPE_VERSION = 1

BATCH_CHECKPOINT_SCHEMA_VERSION = 1
BATCH_CHECKPOINT_FILENAME = "batch_checkpoint.json"


def atomic_write_text(path: Path | str, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(p)
    finally:
        if tmp.exists():
            tmp.unlink()


def atomic_write_json(path: Path | str, payload: Dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True))


def atomic_write_jsonl(path: Path | str, rows: Iterable[Dict[str, Any]]) -> None:
    lines = [json.dumps(row, sort_keys=True) for row in rows]
    text = ("\n".join(lines) + "\n") if lines else ""
    atomic_write_text(path, text)


def atomic_append_jsonl(path: Path | str, payload: Dict[str, Any]) -> None:
    p = Path(path)
    prior = p.read_text(encoding="utf-8") if p.exists() else ""
    line = json.dumps(payload, sort_keys=True) + "\n"
    atomic_write_text(p, prior + line)


def build_batch_checkpoint_payload(batch_id: str, config_fingerprint: str) -> Dict[str, Any]:
    return {
        "schema_version": BATCH_CHECKPOINT_SCHEMA_VERSION,
        "batch_id": batch_id,
        "config_fingerprint": config_fingerprint,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def load_batch_checkpoint(path: Path | str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise RuntimeError(
            f"Resume checkpoint missing: {p}. Re-run without --resume or recreate the batch."
        )
    payload = json.loads(p.read_text(encoding="utf-8"))
    if int(payload.get("schema_version", -1)) != BATCH_CHECKPOINT_SCHEMA_VERSION:
        raise RuntimeError(
            f"Checkpoint schema_version={payload.get('schema_version')} incompatible with "
            f"runner schema_version={BATCH_CHECKPOINT_SCHEMA_VERSION}."
        )
    return payload


def assert_resume_compatible(
    checkpoint: Dict[str, Any],
    expected_fingerprint: str,
    *,
    expected_batch_id: Optional[str] = None,
) -> None:
    checkpoint_batch_id = str(checkpoint.get("batch_id", ""))
    expected_batch_id = str(expected_batch_id) if expected_batch_id is not None else None
    if expected_batch_id is not None and checkpoint_batch_id != expected_batch_id:
        raise RuntimeError(
            "Resume batch mismatch. The checkpoint batch does not match the requested batch "
            f"(checkpoint_batch_id={checkpoint_batch_id}, requested_batch_id={expected_batch_id})."
        )
    checkpoint_fp = str(checkpoint.get("config_fingerprint", ""))
    if checkpoint_fp != expected_fingerprint:
        raise RuntimeError(
            "Resume configuration mismatch. The requested run config does not match the original batch "
            f"(checkpoint_fingerprint={checkpoint_fp}, current_fingerprint={expected_fingerprint})."
        )


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
    openai_base_url: Optional[str] = None
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
            "openai_base_url": self.openai_base_url,
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


def encode_checkpoint_row(
    row: Dict[str, Any],
    *,
    schema_name: str,
    schema_version: int = CHECKPOINT_ENVELOPE_VERSION,
) -> Dict[str, Any]:
    if not isinstance(row, dict):
        raise TypeError("checkpoint row must be a dict")
    return {
        CHECKPOINT_ENVELOPE_SCHEMA_KEY: schema_name,
        CHECKPOINT_ENVELOPE_VERSION_KEY: int(schema_version),
        CHECKPOINT_ENVELOPE_RECORD_KEY: row,
    }


def decode_checkpoint_row(
    payload: Dict[str, Any],
    *,
    schema_name: str,
    supported_versions: Optional[Iterable[int]] = None,
    allow_legacy_flat: bool = True,
) -> tuple[Dict[str, Any], int]:
    if not isinstance(payload, dict):
        raise ValueError("checkpoint row payload must be a JSON object")

    has_schema_marker = (
        CHECKPOINT_ENVELOPE_SCHEMA_KEY in payload or CHECKPOINT_ENVELOPE_VERSION_KEY in payload
    )
    if not has_schema_marker:
        if not allow_legacy_flat:
            raise ValueError("legacy flat checkpoint row is not allowed")
        return payload, 0

    schema = payload.get(CHECKPOINT_ENVELOPE_SCHEMA_KEY)
    if schema != schema_name:
        raise ValueError(f"unexpected checkpoint schema: {schema!r}")

    try:
        version = int(payload.get(CHECKPOINT_ENVELOPE_VERSION_KEY))
    except Exception as exc:
        raise ValueError("checkpoint version is not an integer") from exc

    valid_versions = set(int(v) for v in (supported_versions or [CHECKPOINT_ENVELOPE_VERSION]))
    if version not in valid_versions:
        raise ValueError(
            f"unsupported checkpoint schema version: {version} (supported={sorted(valid_versions)})"
        )

    record = payload.get(CHECKPOINT_ENVELOPE_RECORD_KEY)
    if not isinstance(record, dict):
        raise ValueError("checkpoint envelope record must be an object")
    return record, version


def load_checkpoint_jsonl(
    path: str,
    *,
    schema_name: str,
    supported_versions: Optional[Iterable[int]] = None,
    allow_legacy_flat: bool = True,
) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    p = Path(path)
    stats: Dict[str, int] = {
        "rows_loaded": 0,
        "rows_enveloped": 0,
        "rows_legacy": 0,
        "rows_malformed": 0,
        "rows_invalid": 0,
    }
    if not p.exists():
        return [], stats

    rows: List[Dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            stats["rows_malformed"] += 1
            continue
        if not isinstance(payload, dict):
            stats["rows_invalid"] += 1
            continue
        try:
            row, version = decode_checkpoint_row(
                payload,
                schema_name=schema_name,
                supported_versions=supported_versions,
                allow_legacy_flat=allow_legacy_flat,
            )
        except ValueError:
            stats["rows_invalid"] += 1
            continue
        rows.append(row)
        stats["rows_loaded"] += 1
        if version == 0:
            stats["rows_legacy"] += 1
        else:
            stats["rows_enveloped"] += 1
    return rows, stats


def append_jsonl(
    path: str,
    payload: Dict[str, Any],
    *,
    schema_name: Optional[str] = None,
    schema_version: int = CHECKPOINT_ENVELOPE_VERSION,
) -> None:
    row = (
        encode_checkpoint_row(payload, schema_name=schema_name, schema_version=schema_version)
        if schema_name
        else payload
    )
    atomic_append_jsonl(path, row)


def persist_jsonl(
    path: str,
    payloads: Iterable[Dict[str, Any]],
    *,
    schema_name: Optional[str] = None,
    schema_version: int = CHECKPOINT_ENVELOPE_VERSION,
) -> None:
    p = Path(path)
    rows_to_write = (
        (
            encode_checkpoint_row(row, schema_name=schema_name, schema_version=schema_version)
            if schema_name
            else row
        )
        for row in payloads
    )
    atomic_write_jsonl(p, rows_to_write)
