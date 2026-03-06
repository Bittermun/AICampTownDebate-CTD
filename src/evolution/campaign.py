"""Evolutionary search over debate policy profiles using benchmark fitness."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import copy
import json
import random

import yaml

from src.benchmark import BenchmarkRunResult, BenchmarkPolicy, run_phase1


DIRECTIVE_LIBRARY: Dict[str, str] = {
    "SURVIVAL_FIRST": (
        "Treat bankruptcy as extinction risk. Prefer concise, high-leverage counters and skip low-EV moves."
    ),
    "PRESS_EDGE": (
        "When confidence edge is positive and opponent is weakening, escalate pressure with focused rebuttals."
    ),
    "ADAPT_ON_LOSS": (
        "After losses, explicitly revise strategy: diagnose failure mode, then change evidence style and bet cadence."
    ),
    "ANTI_RAMBLE": (
        "Do not spend tokens on exposition. Produce direct claims with short evidence chains and explicit concessions."
    ),
    "PUNISH_WEAKNESS": (
        "If opponent repeats, contradicts, or evades, target that defect immediately and convert it into judge-facing points."
    ),
    "OPTIONAL_SEARCH": (
        "Use search only when it can change expected judgment materially; otherwise preserve budget."
    ),
}


@dataclass
class StrategyProfile:
    """Genome for one candidate strategy."""

    ev_guard_min_ev: float = -0.03
    ev_guard_edge_scale: float = 0.8
    low_balance_threshold: float = 60.0
    low_balance_bet_cap: float = 10.0
    kelly_enabled: bool = True
    kelly_scale: float = 0.5
    kelly_cap: float = 0.25
    verbosity_scale_enabled: bool = True
    verbosity_base_tokens: int = 600
    directive_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ev_guard_min_ev": self.ev_guard_min_ev,
            "ev_guard_edge_scale": self.ev_guard_edge_scale,
            "low_balance_threshold": self.low_balance_threshold,
            "low_balance_bet_cap": self.low_balance_bet_cap,
            "kelly_enabled": self.kelly_enabled,
            "kelly_scale": self.kelly_scale,
            "kelly_cap": self.kelly_cap,
            "verbosity_scale_enabled": self.verbosity_scale_enabled,
            "verbosity_base_tokens": self.verbosity_base_tokens,
            "directive_ids": list(self.directive_ids),
            "directives": [DIRECTIVE_LIBRARY[d] for d in self.directive_ids if d in DIRECTIVE_LIBRARY],
        }


@dataclass
class CandidateEvaluation:
    """Evaluation output for one candidate against incumbent."""

    candidate_id: str
    generation: int
    profile: StrategyProfile
    fitness: float
    aggregate_score: float
    win_rate_vs_incumbent: float
    mean_balance_edge: float
    final_pass: bool
    gates_pass: bool
    valid_run: bool
    pass_fail: str
    config_path: str
    summary_path: str
    notes: List[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "generation": self.generation,
            "profile": self.profile.to_dict(),
            "fitness": self.fitness,
            "aggregate_score": self.aggregate_score,
            "win_rate_vs_incumbent": self.win_rate_vs_incumbent,
            "mean_balance_edge": self.mean_balance_edge,
            "final_pass": self.final_pass,
            "gates_pass": self.gates_pass,
            "valid_run": self.valid_run,
            "pass_fail": self.pass_fail,
            "config_path": self.config_path,
            "summary_path": self.summary_path,
            "notes": list(self.notes),
            "error": self.error,
        }


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for it in items:
        if it in seen:
            continue
        seen.add(it)
        out.append(it)
    return out


def parse_profile_from_debater_spec(spec: Dict[str, Any]) -> StrategyProfile:
    return StrategyProfile(
        ev_guard_min_ev=float(spec.get("ev_guard_min_ev", -0.03)),
        ev_guard_edge_scale=float(spec.get("ev_guard_edge_scale", 0.8)),
        low_balance_threshold=float(spec.get("low_balance_threshold", 60.0)),
        low_balance_bet_cap=float(spec.get("low_balance_bet_cap", 10.0)),
        kelly_enabled=bool(spec.get("kelly_enabled", True)),
        kelly_scale=float(spec.get("kelly_scale", 0.5)),
        kelly_cap=float(spec.get("kelly_cap", 0.25)),
        verbosity_scale_enabled=bool(spec.get("verbosity_scale_enabled", True)),
        verbosity_base_tokens=int(spec.get("verbosity_base_tokens", 600)),
        directive_ids=[],
    )


def mutate_profile(parent: StrategyProfile, rng: random.Random, mutation_power: float = 1.0) -> StrategyProfile:
    child = copy.deepcopy(parent)
    p = 0.8

    if rng.random() < p:
        child.ev_guard_min_ev = clamp(
            child.ev_guard_min_ev + rng.uniform(-0.05, 0.05) * mutation_power,
            -0.35,
            0.08,
        )
    if rng.random() < p:
        child.ev_guard_edge_scale = clamp(
            child.ev_guard_edge_scale + rng.uniform(-0.25, 0.25) * mutation_power,
            0.2,
            1.8,
        )
    if rng.random() < p:
        child.low_balance_threshold = clamp(
            child.low_balance_threshold + rng.uniform(-35.0, 35.0) * mutation_power,
            20.0,
            240.0,
        )
    if rng.random() < p:
        child.low_balance_bet_cap = clamp(
            child.low_balance_bet_cap + rng.uniform(-7.0, 7.0) * mutation_power,
            2.0,
            40.0,
        )
    if rng.random() < p:
        child.kelly_scale = clamp(child.kelly_scale + rng.uniform(-0.30, 0.30) * mutation_power, 0.05, 1.2)
    if rng.random() < p:
        child.kelly_cap = clamp(child.kelly_cap + rng.uniform(-0.20, 0.20) * mutation_power, 0.05, 0.75)
    if rng.random() < p:
        delta = int(round(rng.uniform(-180, 220) * mutation_power))
        child.verbosity_base_tokens = int(clamp(child.verbosity_base_tokens + delta, 120, 1400))
    if rng.random() < 0.12 * mutation_power:
        child.kelly_enabled = not child.kelly_enabled
    if rng.random() < 0.10 * mutation_power:
        child.verbosity_scale_enabled = not child.verbosity_scale_enabled

    keys = list(DIRECTIVE_LIBRARY.keys())
    directives = list(child.directive_ids)
    if rng.random() < 0.75:
        op = rng.choice(["add", "replace", "drop"])
        if op == "add":
            directives.append(rng.choice(keys))
        elif op == "replace" and directives:
            i = rng.randrange(len(directives))
            directives[i] = rng.choice(keys)
        elif op == "drop" and directives:
            directives.pop(rng.randrange(len(directives)))

    if not directives and rng.random() < 0.75:
        directives.append(rng.choice(keys))
    child.directive_ids = dedupe_keep_order(directives)[:3]
    return child


def profile_signature(profile: StrategyProfile) -> str:
    raw = {
        "ev_guard_min_ev": round(profile.ev_guard_min_ev, 4),
        "ev_guard_edge_scale": round(profile.ev_guard_edge_scale, 4),
        "low_balance_threshold": round(profile.low_balance_threshold, 2),
        "low_balance_bet_cap": round(profile.low_balance_bet_cap, 2),
        "kelly_enabled": profile.kelly_enabled,
        "kelly_scale": round(profile.kelly_scale, 4),
        "kelly_cap": round(profile.kelly_cap, 4),
        "verbosity_scale_enabled": profile.verbosity_scale_enabled,
        "verbosity_base_tokens": int(profile.verbosity_base_tokens),
        "directive_ids": list(profile.directive_ids),
    }
    return json.dumps(raw, sort_keys=True, separators=(",", ":"))


def compose_system_prompt(base_prompt: Optional[str], directive_ids: List[str]) -> str:
    base = (base_prompt or "").strip()
    directives = [DIRECTIVE_LIBRARY[d] for d in directive_ids if d in DIRECTIVE_LIBRARY]
    if not directives:
        return base

    block = "EVOLUTIONARY DIRECTIVES:\n" + "\n".join(f"- {line}" for line in directives)
    if base:
        return f"{base}\n\n{block}"
    return block


def apply_profile(debater_spec: Dict[str, Any], profile: StrategyProfile, base_prompt: Optional[str]) -> None:
    debater_spec["ev_guard_enabled"] = True
    debater_spec["ev_guard_min_ev"] = float(profile.ev_guard_min_ev)
    debater_spec["ev_guard_edge_scale"] = float(profile.ev_guard_edge_scale)
    debater_spec["low_balance_threshold"] = float(profile.low_balance_threshold)
    debater_spec["low_balance_bet_cap"] = float(profile.low_balance_bet_cap)
    debater_spec["kelly_enabled"] = bool(profile.kelly_enabled)
    debater_spec["kelly_scale"] = float(profile.kelly_scale)
    debater_spec["kelly_cap"] = float(profile.kelly_cap)
    debater_spec["verbosity_scale_enabled"] = bool(profile.verbosity_scale_enabled)
    debater_spec["verbosity_base_tokens"] = int(profile.verbosity_base_tokens)
    debater_spec["system_prompt"] = compose_system_prompt(base_prompt, profile.directive_ids)


def build_candidate_config(
    base_config: Dict[str, Any],
    candidate_profile: StrategyProfile,
    incumbent_profile: StrategyProfile,
) -> Dict[str, Any]:
    cfg = copy.deepcopy(base_config)
    models = cfg.setdefault("models", {})
    debaters = models.setdefault("debaters", [])
    if len(debaters) < 2:
        raise ValueError("Tournament config must define at least 2 debaters.")

    base_prompt_a = debaters[0].get("system_prompt")
    base_prompt_b = debaters[1].get("system_prompt")
    apply_profile(debaters[0], candidate_profile, base_prompt_a)
    apply_profile(debaters[1], incumbent_profile, base_prompt_b)
    return cfg


def extract_duel_stats(seed_results: List[Any]) -> tuple[float, float]:
    wins = 0
    total = 0
    balance_edges: List[float] = []

    for seed in seed_results:
        artifact_paths = getattr(seed, "artifact_paths", {}) or {}
        transcript_path = artifact_paths.get("transcript_json")
        if not transcript_path or not Path(transcript_path).exists():
            continue
        payload = json.loads(Path(transcript_path).read_text(encoding="utf-8"))
        cfg = payload.get("config", {})
        debater_a = cfg.get("debater_a")
        debater_b = cfg.get("debater_b")
        winner = payload.get("winner")
        balances = payload.get("final_balances", {})

        if debater_a and winner == debater_a:
            wins += 1
        if debater_a and debater_b and debater_a in balances and debater_b in balances:
            balance_edges.append(float(balances[debater_a]) - float(balances[debater_b]))
        total += 1

    win_rate = float(wins / total) if total else 0.0
    mean_balance_edge = float(sum(balance_edges) / len(balance_edges)) if balance_edges else 0.0
    return win_rate, mean_balance_edge


def compute_fitness(run: BenchmarkRunResult, win_rate: float, mean_balance_edge: float) -> float:
    traj = run.trajectory_summary or {}
    entropy = float(traj.get("mean_entropy_bits", 0.0))
    adapt = float(traj.get("mean_adaptation_gain_after_loss", 0.0))
    pass_shift = float(traj.get("mean_pass_shift", 0.0))

    fitness = float(run.aggregate_score)
    fitness += 0.22 * win_rate
    fitness += 0.10 * clamp(mean_balance_edge / 120.0, -1.0, 1.0)
    fitness += 0.08 * clamp(adapt, -1.0, 1.0)
    fitness += 0.05 * clamp((entropy - 0.5) / 1.5, -1.0, 1.0)
    fitness -= 0.04 * abs(pass_shift)

    if run.final_pass:
        fitness += 0.12
    if not run.gates_pass:
        fitness -= 0.20
    if not run.valid_run:
        fitness -= 0.30
    if run.pass_fail == "dry_run":
        fitness -= 0.05
    return round(float(fitness), 6)


def clone_policy_with_output_paths(
    policy: BenchmarkPolicy, summary_path: str, registry_path: str
) -> BenchmarkPolicy:
    p = copy.deepcopy(policy)
    p.reporting.output_paths.benchmark_summary = summary_path
    p.reporting.output_paths.champion_registry = registry_path
    return p


def evaluate_candidate(
    *,
    policy: BenchmarkPolicy,
    base_config: Dict[str, Any],
    candidate_profile: StrategyProfile,
    incumbent_profile: StrategyProfile,
    candidate_id: str,
    generation: int,
    campaign_dir: Path,
    model_id: str,
    judge_model: Optional[str],
    seeds: List[int],
    fixtures_dir: str,
    allow_stub: bool,
    dry_run: bool,
    source_mode: str,
    enable_model_derived_metrics: bool,
    num_rounds_override: Optional[int],
    max_iterations_override: Optional[int],
) -> CandidateEvaluation:
    candidate_dir = campaign_dir / f"gen_{generation:02d}" / candidate_id
    candidate_dir.mkdir(parents=True, exist_ok=True)
    config_path = candidate_dir / "candidate_config.yaml"
    summary_path = candidate_dir / "benchmark_summary.json"
    registry_path = candidate_dir / "champion_registry.json"

    built = build_candidate_config(base_config, candidate_profile, incumbent_profile)
    config_path.write_text(yaml.safe_dump(built, sort_keys=False), encoding="utf-8")
    local_policy = clone_policy_with_output_paths(policy, str(summary_path), str(registry_path))

    try:
        result = run_phase1(
            policy=local_policy,
            tournament_config_path=str(config_path),
            model_name=model_id,
            judge_model_override=judge_model,
            seeds=seeds,
            fixtures_dir=fixtures_dir,
            allow_stub=allow_stub,
            dry_run=dry_run,
            num_rounds_override=num_rounds_override,
            max_iterations_override=max_iterations_override,
            parent_performer_id=None,
            variant_label=candidate_id,
            refresh_live_cache=False,
            cache_only_live=False,
            artifact_root=str(candidate_dir / "artifacts"),
            source_mode=source_mode,  # type: ignore[arg-type]
            run_label=f"evolution_{candidate_id}",
            enable_model_derived_metrics=enable_model_derived_metrics,
        )
        win_rate, balance_edge = extract_duel_stats(result.seed_results)
        fitness = compute_fitness(result, win_rate, balance_edge)
        payload = result.to_dict()
        payload["evolution"] = {
            "candidate_id": candidate_id,
            "generation": generation,
            "fitness": fitness,
            "win_rate_vs_incumbent": win_rate,
            "mean_balance_edge": balance_edge,
            "candidate_profile": candidate_profile.to_dict(),
            "incumbent_profile": incumbent_profile.to_dict(),
        }
        summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return CandidateEvaluation(
            candidate_id=candidate_id,
            generation=generation,
            profile=copy.deepcopy(candidate_profile),
            fitness=fitness,
            aggregate_score=float(result.aggregate_score),
            win_rate_vs_incumbent=win_rate,
            mean_balance_edge=balance_edge,
            final_pass=bool(result.final_pass),
            gates_pass=bool(result.gates_pass),
            valid_run=bool(result.valid_run),
            pass_fail=result.pass_fail,
            config_path=str(config_path),
            summary_path=str(summary_path),
            notes=list(result.notes),
            error="",
        )
    except Exception as exc:  # pragma: no cover - defensive path for unattended campaigns.
        return CandidateEvaluation(
            candidate_id=candidate_id,
            generation=generation,
            profile=copy.deepcopy(candidate_profile),
            fitness=-1.0,
            aggregate_score=0.0,
            win_rate_vs_incumbent=0.0,
            mean_balance_edge=0.0,
            final_pass=False,
            gates_pass=False,
            valid_run=False,
            pass_fail="error",
            config_path=str(config_path),
            summary_path=str(summary_path),
            notes=[],
            error=str(exc),
        )


def run_evolution_campaign(
    *,
    policy: BenchmarkPolicy,
    base_tournament_config_path: str,
    model_id: str,
    judge_model: Optional[str],
    generations: int,
    population_size: int,
    elite_count: int,
    mutation_power: float,
    rng_seed: int,
    seeds: List[int],
    fixtures_dir: str,
    allow_stub: bool,
    dry_run: bool,
    source_mode: str,
    enable_model_derived_metrics: bool,
    num_rounds_override: Optional[int],
    max_iterations_override: Optional[int],
    judge_variance_runs_override: Optional[int],
    judge_calibration_min_pass_rate_override: Optional[float],
    disable_judge_variance_gate: bool,
    disable_judge_calibration_gate: bool,
    output_dir: str,
) -> Dict[str, Any]:
    if generations < 1:
        raise ValueError("generations must be >= 1")
    if population_size < 2:
        raise ValueError("population_size must be >= 2")
    if elite_count < 1:
        raise ValueError("elite_count must be >= 1")
    if elite_count > population_size:
        raise ValueError("elite_count must be <= population_size")

    base_config = yaml.safe_load(Path(base_tournament_config_path).read_text(encoding="utf-8"))
    models = base_config.get("models", {})
    debaters = models.get("debaters", [])
    if len(debaters) < 2:
        raise ValueError("Tournament config must include at least 2 debaters under models.debaters")

    effective_policy = copy.deepcopy(policy)
    if judge_variance_runs_override is not None:
        effective_policy.runtime.judge_gates.variance.runs = int(judge_variance_runs_override)
    if judge_calibration_min_pass_rate_override is not None:
        effective_policy.runtime.judge_gates.calibration.min_pass_rate = float(
            judge_calibration_min_pass_rate_override
        )
    if disable_judge_variance_gate:
        effective_policy.runtime.judge_gates.variance.enabled = False
    if disable_judge_calibration_gate:
        effective_policy.runtime.judge_gates.calibration.enabled = False

    rng = random.Random(rng_seed)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    campaign_dir = Path(output_dir) / f"evolution_campaign_{run_id}"
    campaign_dir.mkdir(parents=True, exist_ok=True)

    incumbent = parse_profile_from_debater_spec(debaters[0])
    population: List[StrategyProfile] = [copy.deepcopy(incumbent)]
    seen = {profile_signature(incumbent)}
    while len(population) < population_size:
        m = mutate_profile(incumbent, rng=rng, mutation_power=mutation_power)
        sig = profile_signature(m)
        if sig in seen:
            continue
        seen.add(sig)
        population.append(m)

    generation_records: List[Dict[str, Any]] = []
    best_eval: Optional[CandidateEvaluation] = None

    for generation in range(generations):
        evaluations: List[CandidateEvaluation] = []
        for idx, profile in enumerate(population):
            candidate_id = f"g{generation:02d}_c{idx:02d}"
            ev = evaluate_candidate(
                policy=effective_policy,
                base_config=base_config,
                candidate_profile=profile,
                incumbent_profile=incumbent,
                candidate_id=candidate_id,
                generation=generation,
                campaign_dir=campaign_dir,
                model_id=model_id,
                judge_model=judge_model,
                seeds=seeds,
                fixtures_dir=fixtures_dir,
                allow_stub=allow_stub,
                dry_run=dry_run,
                source_mode=source_mode,
                enable_model_derived_metrics=enable_model_derived_metrics,
                num_rounds_override=num_rounds_override,
                max_iterations_override=max_iterations_override,
            )
            evaluations.append(ev)

        evaluations.sort(key=lambda x: x.fitness, reverse=True)
        elites = evaluations[:elite_count]
        champion = elites[0]
        incumbent = copy.deepcopy(champion.profile)
        if best_eval is None or champion.fitness > best_eval.fitness:
            best_eval = copy.deepcopy(champion)

        generation_records.append(
            {
                "generation": generation,
                "champion_candidate_id": champion.candidate_id,
                "champion_fitness": champion.fitness,
                "champion_aggregate_score": champion.aggregate_score,
                "champion_win_rate_vs_incumbent": champion.win_rate_vs_incumbent,
                "champion_profile": champion.profile.to_dict(),
                "leaderboard": [e.to_dict() for e in evaluations],
            }
        )

        parent_pool = [e.profile for e in elites]
        population = [copy.deepcopy(elites[0].profile)]
        seen = {profile_signature(population[0])}
        while len(population) < population_size:
            parent = rng.choice(parent_pool)
            child = mutate_profile(parent, rng=rng, mutation_power=mutation_power)
            sig = profile_signature(child)
            if sig in seen:
                continue
            seen.add(sig)
            population.append(child)

    assert best_eval is not None  # generations >= 1 and population >= 2

    best_config = build_candidate_config(base_config, best_eval.profile, incumbent)
    best_config_path = campaign_dir / "best_candidate_config.yaml"
    best_config_path.write_text(yaml.safe_dump(best_config, sort_keys=False), encoding="utf-8")

    report = {
        "run_id": run_id,
        "campaign_dir": str(campaign_dir),
        "base_tournament_config_path": base_tournament_config_path,
        "model_id": model_id,
        "judge_model": judge_model,
        "generations": generations,
        "population_size": population_size,
        "elite_count": elite_count,
        "mutation_power": mutation_power,
        "rng_seed": rng_seed,
        "seeds": list(seeds),
        "dry_run": dry_run,
        "source_mode": source_mode,
        "enable_model_derived_metrics": enable_model_derived_metrics,
        "judge_gate_overrides": {
            "variance_runs_override": judge_variance_runs_override,
            "calibration_min_pass_rate_override": judge_calibration_min_pass_rate_override,
            "disable_judge_variance_gate": disable_judge_variance_gate,
            "disable_judge_calibration_gate": disable_judge_calibration_gate,
        },
        "best_candidate": best_eval.to_dict(),
        "best_candidate_config": str(best_config_path),
        "generation_records": generation_records,
    }
    report_path = campaign_dir / "campaign_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
