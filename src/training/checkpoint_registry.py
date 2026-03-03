"""Checkpoint registry helpers for training runs."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import json


@dataclass
class CheckpointRecord:
    checkpoint_id: str
    trainer_name: str
    checkpoint_path: str
    created_at: str
    run_id: Optional[str] = None
    parent_checkpoint_id: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _checkpoint_id(checkpoint_path: str, trainer_name: str, run_id: Optional[str]) -> str:
    raw = f"{checkpoint_path}|{trainer_name}|{run_id or ''}|{_now_iso()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def load_checkpoint_registry(path: str) -> List[CheckpointRecord]:
    p = Path(path)
    if not p.exists():
        return []
    payload = json.loads(p.read_text(encoding="utf-8"))
    rows = payload.get("checkpoints", [])
    records: List[CheckpointRecord] = []
    for row in rows:
        records.append(
            CheckpointRecord(
                checkpoint_id=str(row.get("checkpoint_id", "")),
                trainer_name=str(row.get("trainer_name", "unknown")),
                checkpoint_path=str(row.get("checkpoint_path", "")),
                created_at=str(row.get("created_at", _now_iso())),
                run_id=row.get("run_id"),
                parent_checkpoint_id=row.get("parent_checkpoint_id"),
                metrics=dict(row.get("metrics", {}) or {}),
                tags=list(row.get("tags", []) or []),
                metadata=dict(row.get("metadata", {}) or {}),
            )
        )
    return records


def save_checkpoint_registry(records: List[CheckpointRecord], path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": _now_iso(),
        "count": len(records),
        "checkpoints": [r.to_dict() for r in records],
    }
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def register_checkpoint(
    registry_path: str,
    *,
    trainer_name: str,
    checkpoint_path: str,
    run_id: Optional[str] = None,
    parent_checkpoint_id: Optional[str] = None,
    metrics: Optional[Dict[str, float]] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    checkpoint_id: Optional[str] = None,
) -> CheckpointRecord:
    records = load_checkpoint_registry(registry_path)
    record = CheckpointRecord(
        checkpoint_id=checkpoint_id or _checkpoint_id(checkpoint_path, trainer_name, run_id),
        trainer_name=trainer_name,
        checkpoint_path=checkpoint_path,
        created_at=_now_iso(),
        run_id=run_id,
        parent_checkpoint_id=parent_checkpoint_id,
        metrics=metrics or {},
        tags=tags or [],
        metadata=metadata or {},
    )
    records.append(record)
    save_checkpoint_registry(records, registry_path)
    return record
