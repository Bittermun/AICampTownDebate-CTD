"""Phase 1 benchmark orchestrator."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional, Tuple
import hashlib
import json
import platform
import random
import re
import sys

from src.analysis import compute_selection_health, evaluate_judge_calibration, evaluate_judge_variance
from src.arena import EconomyParams, Tournament
from src.arena.observers import MetricsObserver
from src.config_loader import TournamentConfig, load_config
from src.models import Debater, DebaterConfig
from src.models.judge import JudgeConfig, LLMJudge
from src.runtime import normalize_model_path, run_preflight

from .config_models import BenchmarkPolicy, GroupPolicy
from .datasets import HFDatasetAdapter, OfflineFixtureAdapter
from .scoring import score_aggregate, score_group, weighted_group_scores
from .types import BenchmarkRunResult, GateResult, SeedResult


def _hash_dict(value: Dict) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _hash_text(value: Optional[str]) -> str:
    txt = value if value is not None else ""
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()[:16]


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _backend_label(model_name: str) -> str:
    n = normalize_model_path(model_name)
    if n.startswith("ollama:"):
        return "ollama"
    if n.startswith("vllm:"):
        return "vllm"
    if n.startswith("stub"):
        return "stub"
    return "llama_cpp"


def _build_artifact_manifest(paths: Dict[str, str]) -> Dict[str, Dict[str, str]]:
    manifest: Dict[str, Dict[str, str]] = {}
    for key, p in paths.items():
        fp = Path(p)
        if fp.exists():
            manifest[key] = {
                "path": str(fp),
                "sha256": _sha256_file(str(fp)),
            }
    return manifest


def _deterministic_slice(items: list, limit: Optional[int], seed: int) -> list:
    if limit is None or limit >= len(items):
        return items
    start = seed % len(items)
    rotated = items[start:] + items[:start]
    return rotated[:limit]


def _run_seed_gates(
    policy: BenchmarkPolicy,
    judge_model_path: str,
    seed: int,
    allow_stub: bool,
) -> List[GateResult]:
    gates: List[GateResult] = []
    strict_runtime = policy.runtime.strict_mode_required and not allow_stub
    judge = LLMJudge(
        JudgeConfig(
            model_path=judge_model_path,
            name=f"Judge_seed_{seed}",
            randomize_argument_order=False,
            strict_runtime=strict_runtime,
        )
    )
    judge.load_model()
    try:
        if policy.runtime.judge_gates.variance.enabled:
            var = evaluate_judge_variance(
                judge=judge,
                topic="Should cities subsidize public transit?",
                argument_a="Yes, because congestion and emissions are externalities; targeted subsidies can improve net welfare.",
                argument_b="No, transit is always inefficient and subsidies always waste money.",
                runs=policy.runtime.judge_gates.variance.runs,
                max_stdev=policy.runtime.judge_gates.variance.max_stdev,
                min_mean_a=policy.runtime.judge_gates.variance.min_mean_a,
                round_id=seed,
            )
            gates.append(
                GateResult(
                    name="judge_variance",
                    passed=var.passed,
                    details={
                        "mean_confidence_a": var.mean_confidence_a,
                        "stdev_confidence_a": var.stdev_confidence_a,
                        "runs": var.runs,
                    },
                )
            )

        if policy.runtime.judge_gates.calibration.enabled:
            cal = evaluate_judge_calibration(
                judge=judge,
                pass_threshold=policy.runtime.judge_gates.calibration.min_pass_rate,
                round_id=1000 + seed,
            )
            gates.append(
                GateResult(
                    name="judge_calibration",
                    passed=cal.passed,
                    details={
                        "pass_rate": cal.pass_rate,
                        "passed_cases": cal.passed_cases,
                        "total_cases": cal.total_cases,
                    },
                )
            )
    finally:
        judge.unload_model()
    return gates


def _evaluate_group(
    fixture_adapter: OfflineFixtureAdapter,
    hf_adapter: HFDatasetAdapter,
    group_name: str,
    group_policy: GroupPolicy,
    seed: int,
    strict_runtime: bool,
    allow_live_source_fallback: bool,
    live_source_failures: List[Dict],
):
    all_items = []
    degraded_mode = False
    degraded_reasons: List[str] = []
    for d in group_policy.datasets:
        limit = d.sample_size_pairs if d.sample_size_pairs is not None else d.sample_size
        use_live = d.source == "external" and bool(d.hf_dataset_id)
        if use_live:
            try:
                items, degraded = hf_adapter.load(group_name=group_name, dataset_name=d.name, limit=None)
            except Exception as exc:
                if strict_runtime or not allow_live_source_fallback:
                    raise RuntimeError(
                        f"Live dataset pull failed for {group_name}/{d.name}: {exc}"
                    ) from exc
                live_source_failures.append(
                    {
                        "group": group_name,
                        "dataset": d.name,
                        "dataset_id": d.hf_dataset_id,
                        "subset": d.hf_subset,
                        "split": d.split,
                        "error": str(exc),
                        "fallback": "fixture",
                    }
                )
                items, degraded = fixture_adapter.load(group_name=group_name, dataset_name=d.name, limit=None)
                degraded = True
                degraded_reasons.append(f"{group_name}/{d.name}: live pull failed, used fixture fallback")
        else:
            items, degraded = fixture_adapter.load(group_name=group_name, dataset_name=d.name, limit=None)
            if d.source == "external":
                degraded_reasons.append(f"{group_name}/{d.name}: fixture-backed external dataset")
        picked = _deterministic_slice(items, limit=limit, seed=seed)
        all_items.extend(picked)
        degraded_mode = degraded_mode or degraded
    result = score_group(group_name, all_items, group_policy, degraded_mode)
    if degraded_reasons:
        result.reasons.extend(degraded_reasons)
    return result


def _build_seed_tournament(
    tc: TournamentConfig,
    model_name: str,
    judge_model_name: str,
    strict_runtime: bool,
) -> Tuple[Tournament, MetricsObserver]:
    debater_a = Debater(
        DebaterConfig(
            model_path=normalize_model_path(model_name),
            name=f"Debater_{tc.debaters[0].name}",
            system_prompt=tc.debaters[0].system_prompt,
            ev_guard_enabled=tc.debaters[0].ev_guard_enabled,
            ev_guard_min_ev=tc.debaters[0].ev_guard_min_ev,
            ev_guard_edge_scale=tc.debaters[0].ev_guard_edge_scale,
            low_balance_threshold=tc.debaters[0].low_balance_threshold,
            low_balance_bet_cap=tc.debaters[0].low_balance_bet_cap,
            strict_runtime=strict_runtime,
        )
    )
    debater_b = Debater(
        DebaterConfig(
            model_path=normalize_model_path(model_name),
            name=f"Debater_{tc.debaters[1].name}",
            system_prompt=tc.debaters[1].system_prompt,
            ev_guard_enabled=tc.debaters[1].ev_guard_enabled,
            ev_guard_min_ev=tc.debaters[1].ev_guard_min_ev,
            ev_guard_edge_scale=tc.debaters[1].ev_guard_edge_scale,
            low_balance_threshold=tc.debaters[1].low_balance_threshold,
            low_balance_bet_cap=tc.debaters[1].low_balance_bet_cap,
            strict_runtime=strict_runtime,
        )
    )

    judge = LLMJudge(
        JudgeConfig(
            model_path=normalize_model_path(judge_model_name),
            name=tc.judges[0].name or "Judge_Main",
            randomize_argument_order=tc.randomize_argument_order,
            strict_runtime=strict_runtime,
        )
    )

    params = EconomyParams(
        num_rounds=tc.rounds.num_rounds,
        max_iterations=tc.rounds.max_iterations,
        initial_balance=tc.economy.initial_balance,
        max_debt=tc.economy.max_debt,
        tokens_per_round=tc.economy.tokens_per_round,
    )
    observer = MetricsObserver()
    tournament = Tournament(
        debater_a=debater_a,
        debater_b=debater_b,
        judge=judge,
        topics=tc.rounds.topics,
        config=params,
        enable_transcript=True,
        observers=[observer],
        split_pot_enabled=tc.economy.split_pot_enabled,
        initial_pot_amount=tc.economy.initial_pot_amount,
    )
    return tournament, observer


def _run_seed_tournament(
    tc: TournamentConfig,
    model_name: str,
    judge_model_name: str,
    seed: int,
    strict_runtime: bool,
) -> Tuple[Dict[str, str], Dict[str, float]]:
    random.seed(seed)

    tournament, observer = _build_seed_tournament(tc, model_name, judge_model_name, strict_runtime=strict_runtime)
    result = tournament.run()
    seed_dir = Path("logs/benchmark_artifacts") / f"seed_{seed}"
    seed_dir.mkdir(parents=True, exist_ok=True)
    base_path = seed_dir / "tournament_results.json"
    tournament.save_results(str(base_path))
    observer.save(str(seed_dir / "tournament_metrics.json"))

    results_path = seed_dir / "tournament_results.json"
    transcript_path = seed_dir / "tournament_results_transcript.json"
    ledger_path = seed_dir / "tournament_results_ledger.json"
    selection_health_path = seed_dir / "selection_health_dashboard.json"

    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    results_json = json.loads(results_path.read_text(encoding="utf-8"))
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    health = compute_selection_health(transcript=transcript, results=results_json, ledger=ledger)
    health_dict = health.to_dict()
    selection_health_path.write_text(json.dumps(health_dict, indent=2), encoding="utf-8")

    artifact_paths = {
        "results_json": str(results_path),
        "transcript_json": str(transcript_path),
        "ledger_json": str(ledger_path),
        "selection_health_json": str(selection_health_path),
    }

    return artifact_paths, health_dict


def _compute_accounting_drift(ledger_path: str) -> Tuple[float, bool, List[str]]:
    notes: List[str] = []
    ledger = json.loads(Path(ledger_path).read_text(encoding="utf-8"))
    txs = ledger.get("transactions", [])
    balances = ledger.get("balances", {})

    initial_supply = sum(float(t.get("amount", 0.0)) for t in txs if t.get("reason") == "initial_balance" and t.get("from") is None)
    minted = sum(
        float(t.get("amount", 0.0))
        for t in txs
        if t.get("from") is None and t.get("to") is not None and t.get("reason") != "initial_balance"
    )
    burned = sum(float(t.get("amount", 0.0)) for t in txs if t.get("from") is not None and t.get("to") is None)
    final_supply = sum(float(v) for v in balances.values())

    expected_delta = minted - burned
    observed_delta = final_supply - initial_supply
    drift = abs(expected_delta - observed_delta)
    ok = drift <= 0.01
    if not ok:
        notes.append(
            f"Supply drift mismatch: expected_delta={expected_delta:.6f}, observed_delta={observed_delta:.6f}, drift={drift:.6f}"
        )
    return drift, ok, notes


def _extract_round_decisions(transcript: Dict) -> List[Tuple[int, int]]:
    """Return per-round tuple: (pass_count, respond_count)."""
    out = []
    for r in transcript.get("rounds", []):
        pass_count = 0
        respond_count = 0
        for t in r.get("turns", []):
            if t.get("type") != "deliberation":
                continue
            content = t.get("content", "")
            match = re.search(r"\*\*Decision\*\*:\s*(\w+)", content)
            if not match:
                continue
            d = match.group(1).upper()
            if d == "PASS":
                pass_count += 1
            elif d == "RESPOND":
                respond_count += 1
        out.append((pass_count, respond_count))
    return out


def _compute_trajectory_checks(transcript_path: str, health: Dict[str, float], policy: BenchmarkPolicy) -> Tuple[Dict, bool, List[str]]:
    transcript = json.loads(Path(transcript_path).read_text(encoding="utf-8"))
    rounds = transcript.get("rounds", [])
    decisions = _extract_round_decisions(transcript)
    if not rounds:
        return {"enabled": policy.trajectory_checks.enabled, "rounds": 0}, True, []

    mid = max(1, len(decisions) // 2)
    early = decisions[:mid]
    late = decisions[mid:]

    def _rate(bucket: List[Tuple[int, int]]) -> Tuple[float, float]:
        passes = sum(x[0] for x in bucket)
        responds = sum(x[1] for x in bucket)
        total = passes + responds
        if total <= 0:
            return 0.0, 0.0
        return passes / total, responds / total

    pass_early, agg_early = _rate(early)
    pass_late, agg_late = _rate(late if late else early)

    checks = {
        "enabled": policy.trajectory_checks.enabled,
        "rounds": len(rounds),
        "pass_rate_early": round(pass_early, 6),
        "pass_rate_late": round(pass_late, 6),
        "pass_shift": round(pass_late - pass_early, 6),
        "aggression_rate_early": round(agg_early, 6),
        "aggression_rate_late": round(agg_late, 6),
        "aggression_shift": round(agg_late - agg_early, 6),
        "judge_score_entropy_bits": float(health.get("judge_score_entropy_bits", 0.0)),
        "adaptation_gain_after_loss": float(health.get("adaptation_gain_after_loss", 0.0)),
        "mutual_pass_round_rate": float(health.get("mutual_pass_round_rate", 0.0)),
        "pass_rate": float(health.get("pass_rate", 0.0)),
    }
    issues: List[str] = []
    if policy.trajectory_checks.enabled:
        if checks["judge_score_entropy_bits"] < policy.trajectory_checks.min_entropy_bits:
            issues.append(
                f"Trajectory entropy too low: {checks['judge_score_entropy_bits']:.3f} < {policy.trajectory_checks.min_entropy_bits:.3f}"
            )
        if checks["adaptation_gain_after_loss"] < policy.trajectory_checks.min_adaptation_gain_after_loss:
            issues.append(
                "Trajectory adaptation too low: "
                f"{checks['adaptation_gain_after_loss']:.3f} < {policy.trajectory_checks.min_adaptation_gain_after_loss:.3f}"
            )
        if checks["mutual_pass_round_rate"] > policy.trajectory_checks.max_mutual_pass_round_rate:
            issues.append(
                "Mutual pass round rate too high: "
                f"{checks['mutual_pass_round_rate']:.3f} > {policy.trajectory_checks.max_mutual_pass_round_rate:.3f}"
            )
        if checks["pass_rate"] > policy.trajectory_checks.max_pass_rate:
            issues.append(f"Pass rate too high: {checks['pass_rate']:.3f} > {policy.trajectory_checks.max_pass_rate:.3f}")
    return checks, len(issues) == 0, issues


def run_phase1(
    policy: BenchmarkPolicy,
    tournament_config_path: str,
    model_name: str,
    judge_model_override: Optional[str],
    seeds: List[int],
    fixtures_dir: str,
    allow_stub: bool = False,
    dry_run: bool = False,
    num_rounds_override: Optional[int] = None,
    max_iterations_override: Optional[int] = None,
    parent_performer_id: Optional[str] = None,
    variant_label: Optional[str] = None,
) -> BenchmarkRunResult:
    """Run full phase-1 benchmark with live/fixture datasets + real seed artifacts."""
    tc = load_config(tournament_config_path)
    if num_rounds_override is not None:
        tc.rounds.num_rounds = int(num_rounds_override)
    if max_iterations_override is not None:
        tc.rounds.max_iterations = int(max_iterations_override)
    judge_model_configured = judge_model_override or tc.judges[0].model
    judge_model_path = normalize_model_path(judge_model_configured)
    strict_runtime = policy.runtime.strict_mode_required and not allow_stub
    run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    performer_id = _hash_dict({"model": model_name, "judge": judge_model_configured})
    policy_hash = _hash_dict(asdict(policy))
    tournament_config_hash = _hash_dict(asdict(tc))

    model_specs = [
        ("Debater A", model_name),
        ("Debater B", model_name),
        ("BenchmarkJudge", judge_model_configured),
    ]
    if policy.runtime.require_preflight:
        run_preflight(model_specs, allow_stub=allow_stub, allow_backend_fallback=allow_stub)

    if dry_run:
        seed_results = [
            SeedResult(
                seed=seed,
                group_results={},
                aggregate_score=0.0,
                pass_benchmark=False,
                benchmark_score_pass=False,
                gates_pass=False,
                trajectory_pass=True,
            )
            for seed in seeds
        ]
        return BenchmarkRunResult(
            benchmark_id=policy.meta.benchmark_id,
            model_name=model_name,
            judge_name=judge_model_configured,
            seed_results=seed_results,
            group_scores={},
            aggregate_score=0.0,
            benchmark_score_pass=False,
            gates_pass=False,
            validity_pass=True,
            final_pass=False,
            pass_fail="dry_run",
            valid_run=True,
            validity_issues=[],
            gate_summary={"dry_run": True},
            trajectory_summary={},
            degraded_mode=True,
            live_sources_used=[],
            live_source_failures=[],
            degraded_mode_reason="dry_run",
            elo_before_after={"before": 0.0, "after": 0.0},
            tier_before_after={"before": "Unranked", "after": "Unranked"},
            run_metadata={
                "run_id": run_id,
                "performer_id": performer_id,
                "parent_performer_id": parent_performer_id,
                "variant_label": variant_label,
                "policy_hash": policy_hash,
                "tournament_config_hash": tournament_config_hash,
                "seed_set": seeds,
                "num_rounds": tc.rounds.num_rounds,
                "max_iterations": tc.rounds.max_iterations,
                "prompt_hashes": {
                    "debater_a_system_prompt_hash": _hash_text(tc.debaters[0].system_prompt),
                    "debater_b_system_prompt_hash": _hash_text(tc.debaters[1].system_prompt),
                    "judge_system_prompt_hash": _hash_text(None),
                },
                "runtime_fingerprint": {
                    "python_version": sys.version.split()[0],
                    "platform": platform.platform(),
                    "model_backend": _backend_label(model_name),
                    "judge_backend": _backend_label(judge_model_configured),
                    "strict_runtime": strict_runtime,
                    "allow_stub": allow_stub,
                },
            },
        )

    adapter = OfflineFixtureAdapter(fixtures_dir)
    dataset_specs = {}
    for group_name, group_policy in policy.benchmark_groups.items():
        for ds in group_policy.datasets:
            dataset_specs[(group_name, ds.name)] = ds
    hf_adapter = HFDatasetAdapter(dataset_specs=dataset_specs, cache_dir="benchmarks/cache")
    seed_results: List[SeedResult] = []
    aggregate_scores = []
    seed_score_pass_flags = []
    gates_all_pass = True
    any_degraded_mode = False
    overall_validity_issues: List[str] = []
    trajectory_records: List[Dict] = []
    accounting_drifts: List[float] = []
    live_source_failures: List[Dict] = []

    for seed in seeds:
        gates = _run_seed_gates(policy=policy, judge_model_path=judge_model_path, seed=seed, allow_stub=allow_stub)
        gates_pass = all(g.passed for g in gates)
        gates_all_pass = gates_all_pass and gates_pass

        group_results = {}
        for group_name, group_policy in policy.benchmark_groups.items():
            res = _evaluate_group(
                fixture_adapter=adapter,
                hf_adapter=hf_adapter,
                group_name=group_name,
                group_policy=group_policy,
                seed=seed,
                strict_runtime=strict_runtime,
                allow_live_source_fallback=policy.runtime.allow_live_source_fallback,
                live_source_failures=live_source_failures,
            )
            group_results[group_name] = res
            any_degraded_mode = any_degraded_mode or res.degraded_mode

        group_weights = {name: gp.weight for name, gp in policy.benchmark_groups.items()}
        aggregate = weighted_group_scores(group_results, group_weights)
        score_pass = aggregate >= policy.aggregate_scoring.min_pass_score and all(gr.pass_group for gr in group_results.values())
        aggregate_scores.append(aggregate)
        seed_score_pass_flags.append(score_pass)

        artifact_paths, health = _run_seed_tournament(
            tc=tc,
            model_name=model_name,
            judge_model_name=judge_model_configured,
            seed=seed,
            strict_runtime=strict_runtime,
        )

        seed_validity_issues: List[str] = []
        for key in policy.invariants.run_validity.required_artifacts:
            path = artifact_paths.get(key)
            if not path or not Path(path).exists():
                seed_validity_issues.append(f"Missing required artifact: {key}")

        drift, accounting_ok, accounting_notes = _compute_accounting_drift(artifact_paths["ledger_json"])
        accounting_drifts.append(drift)
        if policy.invariants.accounting.fail_on_accounting_drift and drift > policy.invariants.accounting.max_supply_drift_abs:
            seed_validity_issues.append(
                f"Accounting drift {drift:.6f} > {policy.invariants.accounting.max_supply_drift_abs:.6f}"
            )
        seed_validity_issues.extend(accounting_notes)

        trajectory, trajectory_pass, trajectory_issues = _compute_trajectory_checks(
            transcript_path=artifact_paths["transcript_json"],
            health=health,
            policy=policy,
        )
        trajectory_records.append(trajectory)
        seed_validity_issues.extend(trajectory_issues)

        valid_run = len(seed_validity_issues) == 0
        if not valid_run:
            overall_validity_issues.extend(seed_validity_issues)

        seed_results.append(
            SeedResult(
                seed=seed,
                group_results=group_results,
                aggregate_score=round(aggregate, 6),
                pass_benchmark=(score_pass and gates_pass and trajectory_pass and valid_run),
                benchmark_score_pass=score_pass,
                gates_pass=gates_pass,
                trajectory_pass=trajectory_pass,
                gates=gates,
                valid_run=valid_run,
                validity_issues=seed_validity_issues,
                artifact_paths=artifact_paths,
                artifact_manifest=_build_artifact_manifest(artifact_paths),
                accounting_drift_abs=round(drift, 6),
                accounting_ok=accounting_ok,
                accounting_notes=accounting_notes,
                trajectory_checks=trajectory,
            )
        )

    agg = score_aggregate(aggregate_scores, seed_score_pass_flags, policy.aggregate_scoring)
    benchmark_score_pass = agg.benchmark_pass and agg.stability_pass and agg.directional_consistency and all(seed_score_pass_flags)
    validity_pass = all(s.valid_run and s.trajectory_pass for s in seed_results)
    final_pass = benchmark_score_pass and gates_all_pass and validity_pass
    pass_fail = "pass" if final_pass else "fail"

    mean_group_scores: Dict[str, float] = {}
    for group_name in policy.benchmark_groups.keys():
        values = [s.group_results[group_name].score for s in seed_results]
        mean_group_scores[group_name] = round(sum(values) / len(values), 6) if values else 0.0

    trajectory_summary = {
        "seeds": len(trajectory_records),
        "mean_pass_shift": round(mean([float(x.get("pass_shift", 0.0)) for x in trajectory_records]), 6) if trajectory_records else 0.0,
        "mean_aggression_shift": round(
            mean([float(x.get("aggression_shift", 0.0)) for x in trajectory_records]), 6
        )
        if trajectory_records
        else 0.0,
        "mean_entropy_bits": round(
            mean([float(x.get("judge_score_entropy_bits", 0.0)) for x in trajectory_records]), 6
        )
        if trajectory_records
        else 0.0,
        "mean_adaptation_gain_after_loss": round(
            mean([float(x.get("adaptation_gain_after_loss", 0.0)) for x in trajectory_records]), 6
        )
        if trajectory_records
        else 0.0,
    }

    gate_summary = {
        "aggregate_benchmark_pass": agg.benchmark_pass,
        "stability_pass": agg.stability_pass,
        "directional_consistency": agg.directional_consistency,
        "aggregate_score_stdev": agg.aggregate_score_stdev,
        "gates_pass": gates_all_pass,
        "benchmark_score_pass": benchmark_score_pass,
        "validity_pass": validity_pass,
        "final_pass": final_pass,
        "mean_accounting_drift_abs": round(mean(accounting_drifts), 6) if accounting_drifts else 0.0,
        "max_accounting_drift_abs": round(max(accounting_drifts), 6) if accounting_drifts else 0.0,
    }

    metadata_blob = {
        "model_name": model_name,
        "judge_name": judge_model_configured,
        "policy_hash": policy_hash,
        "tournament_config_hash": tournament_config_hash,
        "run_id": run_id,
        "performer_id": performer_id,
        "seed_set": seeds,
    }
    degraded_mode_reason = ""
    if any_degraded_mode:
        if live_source_failures:
            degraded_mode_reason = "fixture fallback used due to live source pull failures"
        else:
            degraded_mode_reason = "fixture-backed datasets in benchmark policy"

    return BenchmarkRunResult(
        benchmark_id=policy.meta.benchmark_id,
        model_name=model_name,
        judge_name=judge_model_configured,
        seed_results=seed_results,
        group_scores=mean_group_scores,
        aggregate_score=agg.aggregate_score_mean,
        benchmark_score_pass=benchmark_score_pass,
        gates_pass=gates_all_pass,
        validity_pass=validity_pass,
        final_pass=final_pass,
        pass_fail=pass_fail,
        valid_run=validity_pass,
        validity_issues=overall_validity_issues,
        gate_summary=gate_summary,
        trajectory_summary=trajectory_summary,
        degraded_mode=any_degraded_mode,
        live_sources_used=hf_adapter.pull_manifest,
        live_source_failures=live_source_failures,
        degraded_mode_reason=degraded_mode_reason,
        elo_before_after={"before": 0.0, "after": 0.0},
        tier_before_after={"before": "Unranked", "after": "Unranked"},
        artifact_paths={
            "results_json": policy.reporting.output_paths.benchmark_summary,
            "champion_registry": policy.reporting.output_paths.champion_registry,
        },
        run_metadata={
            "run_id": run_id,
            "performer_id": performer_id,
            "parent_performer_id": parent_performer_id,
            "variant_label": variant_label,
            "policy_hash": policy_hash,
            "tournament_config_hash": tournament_config_hash,
            "seed_set": seeds,
            "num_rounds": tc.rounds.num_rounds,
            "max_iterations": tc.rounds.max_iterations,
            "model_id": model_name,
            "judge_model_id": judge_model_configured,
            "prompt_hashes": {
                "debater_a_system_prompt_hash": _hash_text(tc.debaters[0].system_prompt),
                "debater_b_system_prompt_hash": _hash_text(tc.debaters[1].system_prompt),
                "judge_system_prompt_hash": _hash_text(None),
            },
            "runtime_fingerprint": {
                "python_version": sys.version.split()[0],
                "platform": platform.platform(),
                "model_backend": _backend_label(model_name),
                "judge_backend": _backend_label(judge_model_configured),
                "strict_runtime": strict_runtime,
                "allow_stub": allow_stub,
            },
            "artifact_manifest": {
                **_build_artifact_manifest(
                    {
                        "summary_json": policy.reporting.output_paths.benchmark_summary,
                        "registry_json": policy.reporting.output_paths.champion_registry,
                    }
                ),
                "live_dataset_pulls": hf_adapter.pull_manifest,
            },
        },
        notes=[f"metadata_hash={_hash_dict(metadata_blob)}"],
    )
