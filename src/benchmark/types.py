"""Core types for benchmark orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BenchmarkItem:
    item_id: str
    group: str
    dataset: str
    prompt: str
    expected: Any = None
    metric_values: Dict[str, float] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    source_ref: str = ""


@dataclass
class GroupScoreResult:
    group_name: str
    score: float
    metric_means: Dict[str, float]
    pass_group: bool
    metric_means_raw: Dict[str, float] = field(default_factory=dict)
    metric_means_transformed: Dict[str, float] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    item_count: int = 0
    degraded_mode: bool = False


@dataclass
class GateResult:
    name: str
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SeedResult:
    seed: int
    group_results: Dict[str, GroupScoreResult]
    aggregate_score: float
    pass_benchmark: bool
    benchmark_score_pass: bool = False
    gates_pass: bool = False
    trajectory_pass: bool = True
    gates: List[GateResult] = field(default_factory=list)
    valid_run: bool = True
    validity_issues: List[str] = field(default_factory=list)
    artifact_paths: Dict[str, str] = field(default_factory=dict)
    artifact_manifest: Dict[str, Dict[str, str]] = field(default_factory=dict)
    accounting_drift_abs: float = 0.0
    accounting_ok: bool = True
    accounting_notes: List[str] = field(default_factory=list)
    trajectory_checks: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AggregateScoreResult:
    aggregate_score_mean: float
    aggregate_score_stdev: float
    benchmark_pass: bool
    stability_pass: bool
    directional_consistency: bool


@dataclass
class BenchmarkRunResult:
    benchmark_id: str
    model_name: str
    judge_name: str
    seed_results: List[SeedResult]
    group_scores: Dict[str, float]
    aggregate_score: float
    benchmark_score_pass: bool
    gates_pass: bool
    validity_pass: bool
    final_pass: bool
    pass_fail: str
    valid_run: bool
    validity_issues: List[str]
    gate_summary: Dict[str, Any]
    trajectory_summary: Dict[str, Any]
    degraded_mode: bool
    live_sources_used: List[Dict[str, Any]]
    live_source_failures: List[Dict[str, Any]]
    degraded_mode_reason: str
    elo_before_after: Dict[str, float]
    tier_before_after: Dict[str, str]
    artifact_paths: Dict[str, str] = field(default_factory=dict)
    run_metadata: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "model_name": self.model_name,
            "judge_name": self.judge_name,
            "seed_results": [
                {
                    "seed": s.seed,
                    "aggregate_score": s.aggregate_score,
                    "pass_benchmark": s.pass_benchmark,
                    "benchmark_score_pass": s.benchmark_score_pass,
                    "gates_pass": s.gates_pass,
                    "trajectory_pass": s.trajectory_pass,
                    "valid_run": s.valid_run,
                    "validity_issues": s.validity_issues,
                    "accounting_drift_abs": s.accounting_drift_abs,
                    "accounting_ok": s.accounting_ok,
                    "accounting_notes": s.accounting_notes,
                    "gates": [{"name": g.name, "passed": g.passed, "details": g.details} for g in s.gates],
                    "group_results": {
                        n: {
                            "score": r.score,
                            "metric_means": r.metric_means,
                            "metric_means_raw": r.metric_means_raw,
                            "metric_means_transformed": r.metric_means_transformed,
                            "pass_group": r.pass_group,
                            "reasons": r.reasons,
                            "item_count": r.item_count,
                            "degraded_mode": r.degraded_mode,
                        }
                        for n, r in s.group_results.items()
                    },
                    "artifact_paths": s.artifact_paths,
                    "artifact_manifest": s.artifact_manifest,
                    "trajectory_checks": s.trajectory_checks,
                }
                for s in self.seed_results
            ],
            "group_scores": self.group_scores,
            "aggregate_score": self.aggregate_score,
            "benchmark_score_pass": self.benchmark_score_pass,
            "gates_pass": self.gates_pass,
            "validity_pass": self.validity_pass,
            "final_pass": self.final_pass,
            "pass_fail": self.pass_fail,
            "valid_run": self.valid_run,
            "validity_issues": self.validity_issues,
            "gate_summary": self.gate_summary,
            "trajectory_summary": self.trajectory_summary,
            "degraded_mode": self.degraded_mode,
            "live_sources_used": self.live_sources_used,
            "live_source_failures": self.live_source_failures,
            "degraded_mode_reason": self.degraded_mode_reason,
            "elo_before_after": self.elo_before_after,
            "tier_before_after": self.tier_before_after,
            "artifact_paths": self.artifact_paths,
            "run_metadata": self.run_metadata,
            "notes": self.notes,
        }
