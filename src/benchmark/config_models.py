"""Typed config models for benchmark_phase1.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


@dataclass
class SeedPolicy:
    seeds: List[int]
    notes: str = ""


@dataclass
class VarianceGate:
    enabled: bool = True
    runs: int = 10
    max_stdev: float = 0.05
    min_mean_a: float = 0.55


@dataclass
class CalibrationGate:
    enabled: bool = True
    min_pass_rate: float = 0.75


@dataclass
class JudgeGates:
    variance: VarianceGate = field(default_factory=VarianceGate)
    calibration: CalibrationGate = field(default_factory=CalibrationGate)


@dataclass
class RuntimePolicy:
    strict_mode_required: bool = True
    require_preflight: bool = True
    allow_stub_for_research: bool = False
    allow_live_source_fallback: bool = True
    judge_gates: JudgeGates = field(default_factory=JudgeGates)


@dataclass
class AccountingInvariantPolicy:
    fail_on_accounting_drift: bool = True
    max_supply_drift_abs: float = 0.01


@dataclass
class RunValidityPolicy:
    fail_on_missing_artifacts: bool = True
    required_artifacts: List[str] = field(default_factory=list)


@dataclass
class InvariantPolicy:
    accounting: AccountingInvariantPolicy = field(default_factory=AccountingInvariantPolicy)
    run_validity: RunValidityPolicy = field(default_factory=RunValidityPolicy)


@dataclass
class DatasetSpec:
    name: str
    source: str
    split: Optional[str] = None
    sample_size: Optional[int] = None
    sample_size_pairs: Optional[int] = None
    hf_dataset_id: Optional[str] = None
    hf_subset: Optional[str] = None
    column_mapping: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GroupThresholds:
    min_mean_roi: Optional[float] = None
    min_adaptation_gain_after_loss: Optional[float] = None
    min_health_score: Optional[float] = None


@dataclass
class MetricTransformSpec:
    type: str = "identity"
    min: Optional[float] = None
    max: Optional[float] = None


@dataclass
class GroupPolicy:
    weight: float
    blocking: bool = True
    datasets: List[DatasetSpec] = field(default_factory=list)
    metric: Optional[str] = None
    metrics: List[str] = field(default_factory=list)
    metric_transforms: Dict[str, MetricTransformSpec] = field(default_factory=dict)
    min_group_score: float = 0.0
    thresholds: Optional[GroupThresholds] = None


@dataclass
class StabilityPolicy:
    max_seed_stdev: float = 0.06
    require_directional_consistency_across_seeds: bool = True


@dataclass
class AggregatePolicy:
    formula: str = "weighted_mean(group_score_i * group_weight_i)"
    min_pass_score: float = 0.60
    stability_requirements: StabilityPolicy = field(default_factory=StabilityPolicy)


@dataclass
class TrajectoryChecksPolicy:
    enabled: bool = True
    min_entropy_bits: float = 0.5
    min_adaptation_gain_after_loss: float = 0.0
    max_mutual_pass_round_rate: float = 1.0
    max_pass_rate: float = 1.0


@dataclass
class ELOKPolicy:
    provisional_matches: int = 30
    k_provisional: int = 32
    k_stable: int = 16


@dataclass
class ELOPolicy:
    initial_rating: float = 1500.0
    k_factor: ELOKPolicy = field(default_factory=ELOKPolicy)
    matchup_window: int = 100


@dataclass
class TierBand:
    name: str
    min_elo: int
    max_elo: int


@dataclass
class LeaguePolicy:
    enabled: bool = True
    description: str = ""
    elo: ELOPolicy = field(default_factory=ELOPolicy)
    tiers: List[TierBand] = field(default_factory=list)


@dataclass
class FreezeRequirements:
    min_windows: int = 3
    min_days_between_windows: int = 3
    require_all_gates_passed_each_window: bool = True
    require_benchmark_pass_each_window: bool = True


@dataclass
class ChallengerPolicy:
    require_head_to_head: bool = True
    min_head_to_head_matches: int = 30
    must_beat_frozen_on: List[str] = field(default_factory=list)
    confidence_interval_required: bool = True
    min_effect_size: float = 0.02


@dataclass
class ChampionFreezePolicy:
    enabled: bool = True
    freeze_requirements: FreezeRequirements = field(default_factory=FreezeRequirements)
    frozen_manifest_fields: List[str] = field(default_factory=list)
    challenger_policy: ChallengerPolicy = field(default_factory=ChallengerPolicy)


@dataclass
class OutputPaths:
    benchmark_summary: str = "logs/benchmark_phase1_summary.json"
    champion_registry: str = "logs/champion_registry.json"


@dataclass
class ReportingPolicy:
    required_summary_fields: List[str] = field(default_factory=list)
    output_paths: OutputPaths = field(default_factory=OutputPaths)


@dataclass
class BenchmarkMeta:
    benchmark_id: str
    owner: str
    version: int
    seed_policy: SeedPolicy


@dataclass
class BenchmarkPolicy:
    meta: BenchmarkMeta
    runtime: RuntimePolicy
    invariants: InvariantPolicy
    benchmark_groups: Dict[str, GroupPolicy]
    aggregate_scoring: AggregatePolicy
    trajectory_checks: TrajectoryChecksPolicy
    league: LeaguePolicy
    champion_freeze: ChampionFreezePolicy
    reporting: ReportingPolicy


def _get_required(data: Dict[str, Any], key: str) -> Any:
    if key not in data:
        raise ValueError(f"Missing required benchmark config field: {key}")
    return data[key]


def load_benchmark_policy(path: str) -> BenchmarkPolicy:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Benchmark policy YAML must be a mapping.")

    meta_raw = _get_required(raw, "meta")
    seed_raw = _get_required(meta_raw, "seed_policy")
    meta = BenchmarkMeta(
        benchmark_id=_get_required(meta_raw, "benchmark_id"),
        owner=_get_required(meta_raw, "owner"),
        version=int(_get_required(meta_raw, "version")),
        seed_policy=SeedPolicy(seeds=list(_get_required(seed_raw, "seeds")), notes=seed_raw.get("notes", "")),
    )

    runtime_raw = _get_required(raw, "runtime")
    jg_raw = runtime_raw.get("judge_gates", {})
    vg_raw = jg_raw.get("variance", {})
    cg_raw = jg_raw.get("calibration", {})
    runtime = RuntimePolicy(
        strict_mode_required=bool(runtime_raw.get("strict_mode_required", True)),
        require_preflight=bool(runtime_raw.get("require_preflight", True)),
        allow_stub_for_research=bool(runtime_raw.get("allow_stub_for_research", False)),
        allow_live_source_fallback=bool(runtime_raw.get("allow_live_source_fallback", True)),
        judge_gates=JudgeGates(
            variance=VarianceGate(
                enabled=bool(vg_raw.get("enabled", True)),
                runs=int(vg_raw.get("runs", 10)),
                max_stdev=float(vg_raw.get("max_stdev", 0.05)),
                min_mean_a=float(vg_raw.get("min_mean_a", 0.55)),
            ),
            calibration=CalibrationGate(
                enabled=bool(cg_raw.get("enabled", True)),
                min_pass_rate=float(cg_raw.get("min_pass_rate", 0.75)),
            ),
        ),
    )

    inv_raw = _get_required(raw, "invariants")
    acc_raw = inv_raw.get("accounting", {})
    rv_raw = inv_raw.get("run_validity", {})
    invariants = InvariantPolicy(
        accounting=AccountingInvariantPolicy(
            fail_on_accounting_drift=bool(acc_raw.get("fail_on_accounting_drift", True)),
            max_supply_drift_abs=float(acc_raw.get("max_supply_drift_abs", 0.01)),
        ),
        run_validity=RunValidityPolicy(
            fail_on_missing_artifacts=bool(rv_raw.get("fail_on_missing_artifacts", True)),
            required_artifacts=list(rv_raw.get("required_artifacts", [])),
        ),
    )

    groups_raw = _get_required(raw, "benchmark_groups")
    benchmark_groups: Dict[str, GroupPolicy] = {}
    for group_name, group_data in groups_raw.items():
        datasets = [
            DatasetSpec(
                name=d["name"],
                source=d.get("source", "internal"),
                split=d.get("split"),
                sample_size=d.get("sample_size"),
                sample_size_pairs=d.get("sample_size_pairs"),
                hf_dataset_id=d.get("hf_dataset_id"),
                hf_subset=d.get("hf_subset"),
                column_mapping=dict(d.get("column_mapping", {})),
            )
            for d in group_data.get("datasets", [])
        ]
        th_raw = group_data.get("thresholds")
        thresholds = None
        if th_raw:
            thresholds = GroupThresholds(
                min_mean_roi=th_raw.get("min_mean_roi"),
                min_adaptation_gain_after_loss=th_raw.get("min_adaptation_gain_after_loss"),
                min_health_score=th_raw.get("min_health_score"),
            )
        benchmark_groups[group_name] = GroupPolicy(
            weight=float(group_data.get("weight", 1.0)),
            blocking=bool(group_data.get("blocking", True)),
            datasets=datasets,
            metric=group_data.get("metric"),
            metrics=list(group_data.get("metrics", [])),
            metric_transforms={
                m: MetricTransformSpec(
                    type=str(spec.get("type", "identity")),
                    min=spec.get("min"),
                    max=spec.get("max"),
                )
                for m, spec in group_data.get("metric_transforms", {}).items()
            },
            min_group_score=float(group_data.get("min_group_score", 0.0)),
            thresholds=thresholds,
        )

    agg_raw = _get_required(raw, "aggregate_scoring")
    st_raw = agg_raw.get("stability_requirements", {})
    aggregate_scoring = AggregatePolicy(
        formula=str(agg_raw.get("formula", "weighted_mean(group_score_i * group_weight_i)")),
        min_pass_score=float(agg_raw.get("min_pass_score", 0.60)),
        stability_requirements=StabilityPolicy(
            max_seed_stdev=float(st_raw.get("max_seed_stdev", 0.06)),
            require_directional_consistency_across_seeds=bool(
                st_raw.get("require_directional_consistency_across_seeds", True)
            ),
        ),
    )

    traj_raw = raw.get("trajectory_checks", {})
    trajectory_checks = TrajectoryChecksPolicy(
        enabled=bool(traj_raw.get("enabled", True)),
        min_entropy_bits=float(traj_raw.get("min_entropy_bits", 0.5)),
        min_adaptation_gain_after_loss=float(traj_raw.get("min_adaptation_gain_after_loss", 0.0)),
        max_mutual_pass_round_rate=float(traj_raw.get("max_mutual_pass_round_rate", 1.0)),
        max_pass_rate=float(traj_raw.get("max_pass_rate", 1.0)),
    )

    league_raw = _get_required(raw, "league")
    elo_raw = league_raw.get("elo", {})
    k_raw = elo_raw.get("k_factor", {})
    tiers = [
        TierBand(name=t["name"], min_elo=int(t["min_elo"]), max_elo=int(t["max_elo"]))
        for t in league_raw.get("tiers", [])
    ]
    league = LeaguePolicy(
        enabled=bool(league_raw.get("enabled", True)),
        description=str(league_raw.get("description", "")),
        elo=ELOPolicy(
            initial_rating=float(elo_raw.get("initial_rating", 1500.0)),
            k_factor=ELOKPolicy(
                provisional_matches=int(k_raw.get("provisional_matches", 30)),
                k_provisional=int(k_raw.get("k_provisional", 32)),
                k_stable=int(k_raw.get("k_stable", 16)),
            ),
            matchup_window=int(elo_raw.get("matchup_window", 100)),
        ),
        tiers=tiers,
    )

    freeze_raw = _get_required(raw, "champion_freeze")
    fr_raw = freeze_raw.get("freeze_requirements", {})
    ch_raw = freeze_raw.get("challenger_policy", {})
    champion_freeze = ChampionFreezePolicy(
        enabled=bool(freeze_raw.get("enabled", True)),
        freeze_requirements=FreezeRequirements(
            min_windows=int(fr_raw.get("min_windows", 3)),
            min_days_between_windows=int(fr_raw.get("min_days_between_windows", 3)),
            require_all_gates_passed_each_window=bool(fr_raw.get("require_all_gates_passed_each_window", True)),
            require_benchmark_pass_each_window=bool(fr_raw.get("require_benchmark_pass_each_window", True)),
        ),
        frozen_manifest_fields=list(freeze_raw.get("frozen_manifest_fields", [])),
        challenger_policy=ChallengerPolicy(
            require_head_to_head=bool(ch_raw.get("require_head_to_head", True)),
            min_head_to_head_matches=int(ch_raw.get("min_head_to_head_matches", 30)),
            must_beat_frozen_on=list(ch_raw.get("must_beat_frozen_on", [])),
            confidence_interval_required=bool(ch_raw.get("confidence_interval_required", True)),
            min_effect_size=float(ch_raw.get("min_effect_size", 0.02)),
        ),
    )

    rep_raw = _get_required(raw, "reporting")
    out_raw = rep_raw.get("output_paths", {})
    reporting = ReportingPolicy(
        required_summary_fields=list(rep_raw.get("required_summary_fields", [])),
        output_paths=OutputPaths(
            benchmark_summary=str(out_raw.get("benchmark_summary", "logs/benchmark_phase1_summary.json")),
            champion_registry=str(out_raw.get("champion_registry", "logs/champion_registry.json")),
        ),
    )

    return BenchmarkPolicy(
        meta=meta,
        runtime=runtime,
        invariants=invariants,
        benchmark_groups=benchmark_groups,
        aggregate_scoring=aggregate_scoring,
        trajectory_checks=trajectory_checks,
        league=league,
        champion_freeze=champion_freeze,
        reporting=reporting,
    )


