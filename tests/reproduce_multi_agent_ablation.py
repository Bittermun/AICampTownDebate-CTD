#!/usr/bin/env python3
"""Run paired multi-agent OFF vs ON tournaments and compare outcomes."""
from __future__ import annotations

import argparse
import json
import random
import sys
from copy import deepcopy
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.arena.observers import MetricsObserver
from src.arena.tournament import EconomyParams, Tournament
from src.config_loader import load_config
from src.models import Debater, DebaterConfig
from src.models.judge import JudgeConfig, LLMJudge
from src.runtime import normalize_model_path, print_preflight, run_preflight


def _parse_seeds(raw: str) -> List[int]:
    seeds = [int(x.strip()) for x in raw.split(",") if x.strip()]
    if not seeds:
        raise ValueError("At least one seed is required.")
    return seeds


def _safe_mean(values: List[float]) -> float:
    return float(mean(values)) if values else 0.0


def _build_participants(cfg):
    d0 = cfg.debaters[0]
    d1 = cfg.debaters[1]
    debater_a = Debater(
        DebaterConfig(
            model_path=normalize_model_path(d0.model),
            name=f"Debater_{d0.name}",
            system_prompt=d0.system_prompt,
            ev_guard_enabled=d0.ev_guard_enabled,
            ev_guard_min_ev=d0.ev_guard_min_ev,
            ev_guard_edge_scale=d0.ev_guard_edge_scale,
            low_balance_threshold=d0.low_balance_threshold,
            low_balance_bet_cap=d0.low_balance_bet_cap,
            kelly_enabled=d0.kelly_enabled,
            kelly_scale=d0.kelly_scale,
            kelly_cap=d0.kelly_cap,
            verbosity_scale_enabled=d0.verbosity_scale_enabled,
            verbosity_base_tokens=d0.verbosity_base_tokens,
            initial_balance_ref=cfg.economy.initial_balance,
            multi_agent_enabled=d0.multi_agent_enabled,
            multi_agent_mode=d0.multi_agent_mode,
            multi_agent_max_tokens=d0.multi_agent_max_tokens,
            multi_agent_min_balance=d0.multi_agent_min_balance,
        )
    )
    debater_b = Debater(
        DebaterConfig(
            model_path=normalize_model_path(d1.model),
            name=f"Debater_{d1.name}",
            system_prompt=d1.system_prompt,
            ev_guard_enabled=d1.ev_guard_enabled,
            ev_guard_min_ev=d1.ev_guard_min_ev,
            ev_guard_edge_scale=d1.ev_guard_edge_scale,
            low_balance_threshold=d1.low_balance_threshold,
            low_balance_bet_cap=d1.low_balance_bet_cap,
            kelly_enabled=d1.kelly_enabled,
            kelly_scale=d1.kelly_scale,
            kelly_cap=d1.kelly_cap,
            verbosity_scale_enabled=d1.verbosity_scale_enabled,
            verbosity_base_tokens=d1.verbosity_base_tokens,
            initial_balance_ref=cfg.economy.initial_balance,
            multi_agent_enabled=d1.multi_agent_enabled,
            multi_agent_mode=d1.multi_agent_mode,
            multi_agent_max_tokens=d1.multi_agent_max_tokens,
            multi_agent_min_balance=d1.multi_agent_min_balance,
        )
    )
    judge = LLMJudge(
        JudgeConfig(
            model_path=normalize_model_path(cfg.judges[0].model),
            name="Judge_Main",
            randomize_argument_order=cfg.randomize_argument_order,
        )
    )
    return debater_a, debater_b, judge


def _extract_round_metrics(rounds) -> Dict[str, float]:
    pass_rates: List[float] = []
    aggressions: List[float] = []
    rois: List[float] = []
    outflows: List[float] = []
    gen_costs: List[float] = []
    validation_fallbacks: List[float] = []
    economy_mentions: List[float] = []

    for r in rounds:
        for rep in getattr(r, "observation_reports", []):
            if rep.observer_name != "MetricsObserver":
                continue
            m = rep.metrics
            a = m.get("debater_a", {})
            b = m.get("debater_b", {})

            pass_rates.extend([float(a.get("pass_rate", 0.0)), float(b.get("pass_rate", 0.0))])
            aggressions.extend([float(a.get("aggression", 0.0)), float(b.get("aggression", 0.0))])

            for roi in (a.get("roi"), b.get("roi")):
                if roi is not None:
                    rois.append(float(roi))

            outflows.extend([float(a.get("outflow", 0.0)), float(b.get("outflow", 0.0))])
            gen_costs.extend([float(a.get("gen_cost", 0.0)), float(b.get("gen_cost", 0.0))])
            validation_fallbacks.extend(
                [float(a.get("validation_fallbacks", 0.0)), float(b.get("validation_fallbacks", 0.0))]
            )
            economy_mentions.extend([float(a.get("economy_mentions", 0.0)), float(b.get("economy_mentions", 0.0))])

    return {
        "avg_pass_rate": round(_safe_mean(pass_rates), 4),
        "avg_aggression": round(_safe_mean(aggressions), 4),
        "avg_roi": round(_safe_mean(rois), 4) if rois else 0.0,
        "avg_outflow": round(_safe_mean(outflows), 4),
        "avg_gen_cost": round(_safe_mean(gen_costs), 4),
        "avg_validation_fallbacks": round(_safe_mean(validation_fallbacks), 4),
        "avg_economy_mentions": round(_safe_mean(economy_mentions), 4),
    }


def _run_condition(cfg, mode_name: str, seed: int) -> Dict[str, Any]:
    random.seed(seed)
    debater_a, debater_b, judge = _build_participants(cfg)
    observer = MetricsObserver()
    econ = EconomyParams(
        num_rounds=cfg.rounds.num_rounds,
        max_iterations=cfg.rounds.max_iterations,
        initial_balance=cfg.economy.initial_balance,
        max_debt=cfg.economy.max_debt,
        tokens_per_round=cfg.economy.tokens_per_round,
        betting_fee=0.05,
        min_bet=5.0,
    )
    tournament = Tournament(
        debater_a=debater_a,
        debater_b=debater_b,
        judge=judge,
        topics=cfg.rounds.topics,
        config=econ,
        enable_transcript=False,
        observers=[observer],
        split_pot_enabled=cfg.economy.split_pot_enabled,
        initial_pot_amount=cfg.economy.initial_pot_amount,
    )
    result = tournament.run()
    final_balances = result.final_balances
    keys = list(final_balances.keys())
    spread = 0.0
    if len(keys) >= 2:
        spread = abs(float(final_balances.get(keys[0], 0.0)) - float(final_balances.get(keys[1], 0.0)))

    metrics = _extract_round_metrics(result.rounds)
    return {
        "mode": mode_name,
        "seed": seed,
        "winner": result.winner,
        "final_balances": final_balances,
        "rounds_completed": len(result.rounds),
        "final_balance_spread": round(spread, 4),
        **metrics,
    }


def _set_multi_agent(cfg, enabled: bool):
    for d in cfg.debaters:
        d.multi_agent_enabled = bool(enabled)
        if not enabled:
            d.multi_agent_mode = "none"


def _delta(on: Dict[str, Any], off: Dict[str, Any]) -> Dict[str, float]:
    keys = [
        "final_balance_spread",
        "avg_pass_rate",
        "avg_aggression",
        "avg_roi",
        "avg_outflow",
        "avg_gen_cost",
        "avg_validation_fallbacks",
        "avg_economy_mentions",
    ]
    out: Dict[str, float] = {}
    for k in keys:
        out[f"{k}_on_minus_off"] = round(float(on.get(k, 0.0)) - float(off.get(k, 0.0)), 4)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Paired multi-agent ON/OFF ablation")
    parser.add_argument("--config", default="configs/multi_agent_experimental.yaml")
    parser.add_argument("--seeds", default="101,202,303")
    parser.add_argument("--rounds", type=int, default=3, help="Override rounds for faster runs")
    parser.add_argument("--allow-stub", action="store_true")
    parser.add_argument("--output", default="logs/multi_agent_ablation.json")
    args = parser.parse_args()

    seeds = _parse_seeds(args.seeds)
    cfg = load_config(args.config)
    cfg.rounds.num_rounds = max(1, int(args.rounds))
    cfg.rounds.topics = cfg.rounds.topics[: cfg.rounds.num_rounds]

    model_specs = [
        ("Debater A", cfg.debaters[0].model),
        ("Debater B", cfg.debaters[1].model),
        ("Judge", cfg.judges[0].model),
    ]
    try:
        preflight = run_preflight(
            model_specs,
            allow_stub=args.allow_stub,
            allow_backend_fallback=args.allow_stub,
        )
    except RuntimeError as e:
        print(str(e))
        return 1
    print_preflight(preflight)

    per_seed: List[Dict[str, Any]] = []
    for seed in seeds:
        cfg_off = deepcopy(cfg)
        cfg_on = deepcopy(cfg)
        _set_multi_agent(cfg_off, enabled=False)
        _set_multi_agent(cfg_on, enabled=True)

        print(f"\n[seed {seed}] running OFF condition...")
        off = _run_condition(cfg_off, "multi_agent_off", seed=seed)
        print(f"[seed {seed}] running ON condition...")
        on = _run_condition(cfg_on, "multi_agent_on", seed=seed)
        per_seed.append(
            {
                "seed": seed,
                "off": off,
                "on": on,
                "delta_on_minus_off": _delta(on=on, off=off),
            }
        )

    def _mean_delta(metric_key: str) -> float:
        vals = [float(s["delta_on_minus_off"].get(metric_key, 0.0)) for s in per_seed]
        return round(_safe_mean(vals), 4)

    mean_delta = {
        "final_balance_spread_on_minus_off": _mean_delta("final_balance_spread_on_minus_off"),
        "avg_pass_rate_on_minus_off": _mean_delta("avg_pass_rate_on_minus_off"),
        "avg_aggression_on_minus_off": _mean_delta("avg_aggression_on_minus_off"),
        "avg_roi_on_minus_off": _mean_delta("avg_roi_on_minus_off"),
        "avg_outflow_on_minus_off": _mean_delta("avg_outflow_on_minus_off"),
        "avg_gen_cost_on_minus_off": _mean_delta("avg_gen_cost_on_minus_off"),
        "avg_validation_fallbacks_on_minus_off": _mean_delta("avg_validation_fallbacks_on_minus_off"),
        "avg_economy_mentions_on_minus_off": _mean_delta("avg_economy_mentions_on_minus_off"),
    }

    report = {
        "config": args.config,
        "rounds": cfg.rounds.num_rounds,
        "seeds": seeds,
        "conditions": {
            "off": {"multi_agent_enabled": False},
            "on": {"multi_agent_enabled": True},
        },
        "per_seed": per_seed,
        "mean_delta_on_minus_off": mean_delta,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nSaved multi-agent ablation report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
