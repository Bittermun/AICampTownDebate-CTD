"""Minimal trainer interfaces to decouple pipeline orchestration from backends."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol
import uuid


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TrainingStageResult:
    stage: str
    success: bool
    checkpoint_path: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrainingRunResult:
    run_id: str
    trainer_name: str
    started_at: str
    finished_at: str
    stages: List[TrainingStageResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        out = asdict(self)
        out["stages"] = [s.to_dict() for s in self.stages]
        return out


class TrainerInterface(Protocol):
    """Backend-agnostic training API for SFT and preference stages."""

    name: str

    def run(
        self,
        *,
        sft_dataset_path: Optional[str] = None,
        preference_dataset_path: Optional[str] = None,
        base_checkpoint_path: Optional[str] = None,
        output_dir: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> TrainingRunResult:
        ...


class NoOpTrainer:
    """
    Deterministic trainer stub used for wiring tests and dry runs.

    This lets us exercise data + registry flows without provisioning GPU trainers.
    """

    name = "noop_trainer"

    def run(
        self,
        *,
        sft_dataset_path: Optional[str] = None,
        preference_dataset_path: Optional[str] = None,
        base_checkpoint_path: Optional[str] = None,
        output_dir: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> TrainingRunResult:
        _ = output_dir
        _ = config
        started = _now_iso()
        stages: List[TrainingStageResult] = []

        if sft_dataset_path:
            stages.append(
                TrainingStageResult(
                    stage="sft",
                    success=True,
                    checkpoint_path=base_checkpoint_path,
                    metrics={"examples_seen": 0.0},
                    notes=[f"dry-run consumed {sft_dataset_path}"],
                )
            )
        if preference_dataset_path:
            stages.append(
                TrainingStageResult(
                    stage="preference",
                    success=True,
                    checkpoint_path=base_checkpoint_path,
                    metrics={"pairs_seen": 0.0},
                    notes=[f"dry-run consumed {preference_dataset_path}"],
                )
            )

        return TrainingRunResult(
            run_id=f"train_{uuid.uuid4().hex[:12]}",
            trainer_name=self.name,
            started_at=started,
            finished_at=_now_iso(),
            stages=stages,
            metadata={"base_checkpoint_path": base_checkpoint_path},
        )
