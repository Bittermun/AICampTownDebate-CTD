#!/usr/bin/env python3
"""Awareness probe suite with structured data capture.

This suite complements `tests/probe_meta_awareness.py` by adding repeatable,
multi-scenario probes and machine-readable outputs for analysis.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import random
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config_loader import load_config
from src.models.judge import JudgeConfig, LLMJudge
from src.models.openai_compat_backend import OpenAICompatBackend, OpenAICompatConfig
from src.models import BetType, Debater, DebaterConfig
from src.prompting import load_rule_card, render_rule_view
from src.runtime import normalize_model_path, print_preflight, run_preflight


@dataclass
class ProbeRecord:
    run_id: str
    trial_index: int
    debater_name: str
    model_id: str
    scenario: str
    passed: bool
    score: float
    max_score: float
    checks: Dict[str, Any]
    prompt: str
    response: str
    tokens_used: int
    tokens_used_estimated: bool


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _persist_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def _contains_any(text: str, patterns: List[str]) -> bool:
    t = text.lower()
    return any(p.lower() in t for p in patterns)


def _parse_json_object_from_text(text: str) -> Dict[str, Any]:
    """Best-effort parse of a JSON object embedded in model output."""
    raw = text.strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group())
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return {}
    return {}


def _effective_tokens(tokens_used: int, text: str) -> Tuple[int, bool]:
    """Return provider tokens when available, otherwise estimate from length."""
    if tokens_used > 0:
        return int(tokens_used), False
    # Lightweight fallback estimate: ~1.3 tokens per word, minimum 1
    est = max(1, int(round(len(text.split()) * 1.3)))
    return est, True


def _is_error_like_response(text: str) -> bool:
    t = text.upper()
    return any(x in t for x in ["[OPENAI_COMPAT_ERROR]", "[OPENAI_COMPAT_UNAVAILABLE]", "[VLLM_ERROR]", "[ERROR]", "[STUB]"])


def _score_rule_recall(response: str) -> Tuple[float, float, Dict[str, Any]]:
    obj = _parse_json_object_from_text(response)
    if obj:
        bankruptcy_rule = str(obj.get("bankruptcy_rule", "")).lower()
        fee_rule = str(obj.get("fee_rule", "")).lower()
        pass_respond_tradeoff = str(obj.get("pass_respond_tradeoff", "")).lower()
        cost_components = obj.get("cost_components", [])
        if not isinstance(cost_components, list):
            cost_components = []
        cost_components_l = [str(x).lower() for x in cost_components]
        checks = {
            "mentions_bankruptcy_elimination": _contains_any(bankruptcy_rule, ["<= 0", "zero", "bankrupt", "eliminat"]),
            "mentions_hold_vs_respond_cost": _contains_any(pass_respond_tradeoff, ["hold", "respond"])
            and _contains_any(pass_respond_tradeoff, ["cost", "fee", "spend", "token"]),
            "mentions_iteration_fee_growth": _contains_any(fee_rule, ["increase", "iteration", "5%", "rises"]),
            "mentions_generation_or_deliberation_cost": any(
                x in cost_components_l for x in ["generation", "deliberation", "search", "bet_fee"]
            ),
            "json_parsed": True,
        }
        score = float(sum(1 for k, v in checks.items() if k != "json_parsed" and v))
        return score, 4.0, checks
    t = response.lower()
    checks = {
        "mentions_bankruptcy_elimination": _contains_any(t, ["bankrupt", "eliminat", "<= 0", "zero balance"]),
        "mentions_hold_vs_respond_cost": _contains_any(t, ["hold", "respond"]) and _contains_any(
            t, ["cost", "fee", "spend", "token"]
        ),
        "mentions_iteration_fee_growth": _contains_any(t, ["fee"]) and _contains_any(
            t, ["increase", "iteration", "5%", "rises"]
        ),
        "mentions_generation_or_deliberation_cost": _contains_any(t, ["generation", "deliberation", "token cost"]),
        "json_parsed": False,
    }
    score = float(sum(1 for v in checks.values() if v))
    return score, 4.0, checks


def _score_counterfactual(response: str) -> Tuple[float, float, Dict[str, Any]]:
    obj = _parse_json_object_from_text(response)
    if obj:
        action = str(obj.get("action", "")).lower()
        rationale = str(obj.get("economic_rationale", "")).lower()
        chooses_pass = action in {"pass", "hold"}
        mentions_low_balance = _contains_any(rationale, ["low balance", "balance", "capital", "bankrupt", "eliminat", "18"])
        mentions_high_fee = _contains_any(rationale, ["fee", "cost", "expensive", "25%"])
        checks = {
            "chooses_conservative_action": chooses_pass,
            "mentions_balance_risk": mentions_low_balance,
            "mentions_fee_pressure": mentions_high_fee,
            "json_parsed": True,
        }
        score = float(sum(1 for k, v in checks.items() if k != "json_parsed" and v))
        return score, 3.0, checks
    t = response.lower()
    chooses_pass = _contains_any(t, ["hold", "pass", "do not respond"])
    mentions_low_balance = _contains_any(t, ["low balance", "balance", "capital", "bankrupt", "eliminat"])
    mentions_high_fee = _contains_any(t, ["fee", "cost", "expensive", "25%"])
    checks = {
        "chooses_conservative_action": chooses_pass,
        "mentions_balance_risk": mentions_low_balance,
        "mentions_fee_pressure": mentions_high_fee,
        "json_parsed": False,
    }
    score = float(sum(1 for v in checks.values() if v))
    return score, 3.0, checks


def _score_adversarial_correction(response: str) -> Tuple[float, float, Dict[str, Any]]:
    obj = _parse_json_object_from_text(response)
    if obj:
        verdict = str(obj.get("verdict", "")).lower()
        corrected_bankruptcy = str(obj.get("corrected_bankruptcy_rule", "")).lower()
        corrected_fee = str(obj.get("corrected_fee_rule", "")).lower()
        rejects_false = verdict in {"false", "incorrect", "wrong"}
        fixes_bankruptcy = _contains_any(corrected_bankruptcy, ["<= 0", "bankrupt", "eliminat", "zero"])
        fixes_fee = _contains_any(corrected_fee, ["increase", "iteration", "5%", "rises"])
        checks = {
            "rejects_false_claim": rejects_false,
            "corrects_bankruptcy_rule": fixes_bankruptcy,
            "corrects_fee_dynamics": fixes_fee,
            "json_parsed": True,
        }
        score = float(sum(1 for k, v in checks.items() if k != "json_parsed" and v))
        return score, 3.0, checks
    t = response.lower()
    rejects_false = _contains_any(t, ["incorrect", "false", "not true", "wrong"])
    fixes_bankruptcy = _contains_any(t, ["bankrupt", "eliminat", "<= 0", "zero"])
    fixes_fee = _contains_any(t, ["fee"]) and _contains_any(t, ["increase", "iteration", "5%", "rises"])
    checks = {
        "rejects_false_claim": rejects_false,
        "corrects_bankruptcy_rule": fixes_bankruptcy,
        "corrects_fee_dynamics": fixes_fee,
        "json_parsed": False,
    }
    score = float(sum(1 for v in checks.values() if v))
    return score, 3.0, checks


def _extract_action(response: str) -> str:
    obj = _parse_json_object_from_text(response)
    if obj:
        for key in ("action", "decision"):
            val = str(obj.get(key, "")).strip().lower()
            if val in {"pass", "hold", "respond"}:
                return val
    t = response.lower()
    if re.search(r"\bhold\b", t):
        return "hold"
    if re.search(r"\bpass\b", t):
        return "pass"
    if re.search(r"\brespond\b", t):
        return "respond"
    return "unknown"


def _score_consistency(first: str, second: str) -> Tuple[float, float, Dict[str, Any]]:
    action_1 = _extract_action(first)
    action_2 = _extract_action(second)
    checks = {
        "action_detected_prompt1": action_1 != "unknown",
        "action_detected_prompt2": action_2 != "unknown",
        "action_consistent": action_1 == action_2 and action_1 != "unknown",
    }
    score = float(sum(1 for v in checks.values() if v))
    checks["action_1"] = action_1
    checks["action_2"] = action_2
    return score, 3.0, checks


def _call_model(debater: Debater, prompt: str, system: str, max_tokens: int = 220) -> Tuple[str, int]:
    result = debater._generate(prompt=prompt, system=system, max_tokens=max_tokens, json_mode=False, temperature=0.0)
    return result.text.strip(), int(result.tokens_used)


def _run_text_probe(
    *,
    run_id: str,
    trial_index: int,
    debater: Debater,
    model_id: str,
    scenario: str,
    prompt: str,
    scoring_fn,
    judge: LLMJudge | None = None,
) -> ProbeRecord:
    system = (
        "You are being evaluated for explicit tournament-economy awareness. "
        "Return valid JSON only, with exact fields requested by the prompt."
    )
    response, raw_tokens_used = _call_model(debater, prompt, system)
    tokens_used, tokens_estimated = _effective_tokens(raw_tokens_used, response)
    score, max_score, checks = scoring_fn(response)
    checks["error_like_response"] = _is_error_like_response(response)
    if judge is not None:
        j_score, j_pass, j_reason = _judge_grade_response(judge=judge, scenario_prompt=prompt, candidate_response=response)
        checks["judge_awareness_score"] = round(j_score, 6)
        checks["judge_awareness_pass"] = j_pass
        checks["judge_awareness_reasoning"] = j_reason[:300]
    passed = score >= max_score - 0.5
    return ProbeRecord(
        run_id=run_id,
        trial_index=trial_index,
        debater_name=debater.name,
        model_id=model_id,
        scenario=scenario,
        passed=passed,
        score=score,
        max_score=max_score,
        checks=checks,
        prompt=prompt,
        response=response,
        tokens_used=tokens_used,
        tokens_used_estimated=tokens_estimated,
    )


def _run_consistency_probe(
    *,
    run_id: str,
    trial_index: int,
    debater: Debater,
    model_id: str,
) -> ProbeRecord:
    system = "Return strict JSON only."
    prompt_1 = (
        "State: balance=18, confidence_self=0.44, confidence_opponent=0.56, current_fee_rate=0.25. "
        "Return JSON with fields: action(HOLD|RESPOND), reason_short, and one numeric_reference."
    )
    prompt_2 = (
        "Same state restated: low balance (18), trailing confidence, and high fee (25%). "
        "Return JSON with fields: action(HOLD|RESPOND), reason_short, and one numeric_reference."
    )
    response_1, tk_1_raw = _call_model(debater, prompt_1, system, max_tokens=140)
    response_2, tk_2_raw = _call_model(debater, prompt_2, system, max_tokens=140)
    tk_1, est_1 = _effective_tokens(tk_1_raw, response_1)
    tk_2, est_2 = _effective_tokens(tk_2_raw, response_2)
    score, max_score, checks = _score_consistency(response_1, response_2)
    checks["error_like_response_1"] = _is_error_like_response(response_1)
    checks["error_like_response_2"] = _is_error_like_response(response_2)
    passed = bool(checks.get("action_consistent"))
    return ProbeRecord(
        run_id=run_id,
        trial_index=trial_index,
        debater_name=debater.name,
        model_id=model_id,
        scenario="consistency_hold_respond",
        passed=passed,
        score=score,
        max_score=max_score,
        checks=checks,
        prompt=prompt_1 + "\n\n---\n\n" + prompt_2,
        response=f"[1] {response_1}\n\n[2] {response_2}",
        tokens_used=tk_1 + tk_2,
        tokens_used_estimated=bool(est_1 or est_2),
    )


def _run_action_policy_probe(
    *,
    run_id: str,
    trial_index: int,
    debater: Debater,
    model_id: str,
) -> ProbeRecord:
    low_state = debater.decide_bet(
        balance=18.0,
        opponent_argument="Opponent has a slight lead and strong rebuttal.",
        own_argument="My prior claim is weakly supported.",
        confidence_self=0.44,
        confidence_opponent=0.56,
        current_fee_rate=0.25,
    )
    high_state = debater.decide_bet(
        balance=300.0,
        opponent_argument="Opponent argument has several unsupported claims.",
        own_argument="I can provide better evidence.",
        confidence_self=0.63,
        confidence_opponent=0.37,
        current_fee_rate=0.05,
    )
    checks = {
        "low_balance_conservative": low_state.bet_type == BetType.PASS or low_state.amount <= 10.0,
        "high_state_engages": high_state.bet_type == BetType.RESPOND and high_state.amount > 0.0,
        "policy_sensitive_to_state": (low_state.bet_type != high_state.bet_type)
        or (float(low_state.amount) < float(high_state.amount)),
        "intent_present_low": bool((low_state.intent or "").strip()),
        "intent_present_high": bool((high_state.intent or "").strip()),
        "rule_refs_present_low": bool(low_state.rule_refs_used),
        "rule_refs_present_high": bool(high_state.rule_refs_used),
        "action_label_consistent_low": (low_state.action_label or "") == ("HOLD" if low_state.bet_type == BetType.PASS else "RESPOND"),
        "action_label_consistent_high": (high_state.action_label or "") == ("HOLD" if high_state.bet_type == BetType.PASS else "RESPOND"),
        "low_action": low_state.bet_type.value,
        "low_amount": low_state.amount,
        "high_action": high_state.bet_type.value,
        "high_amount": high_state.amount,
        "error_like_low_reasoning": _is_error_like_response(low_state.reasoning),
        "error_like_high_reasoning": _is_error_like_response(high_state.reasoning),
    }
    score = float(
        sum(
            1
            for key in ("low_balance_conservative", "high_state_engages", "policy_sensitive_to_state")
            if checks[key]
        )
    )
    raw_tokens = int(low_state.llm_tokens_used + high_state.llm_tokens_used)
    tok_text = f"{low_state.reasoning}\n{high_state.reasoning}"
    tokens_used, tokens_estimated = _effective_tokens(raw_tokens, tok_text)
    return ProbeRecord(
        run_id=run_id,
        trial_index=trial_index,
        debater_name=debater.name,
        model_id=model_id,
        scenario="action_policy_economy_hold_respond",
        passed=bool(checks["low_balance_conservative"] and checks["policy_sensitive_to_state"]),
        score=score,
        max_score=3.0,
        checks=checks,
        prompt="Internal decide_bet probes: low-balance/high-fee and high-balance/high-edge states.",
        response=f"low={low_state.reasoning[:240]} | high={high_state.reasoning[:240]}",
        tokens_used=tokens_used,
        tokens_used_estimated=tokens_estimated,
    )


def _resolve_openai_model_path(model_path: str) -> Tuple[str, str]:
    """Resolve openai:<id> to an actually exposed /v1/models id when needed."""
    if not model_path.startswith("openai:"):
        return model_path, "unchanged"
    configured = model_path.split(":", 1)[1]
    backend = OpenAICompatBackend(OpenAICompatConfig(model=configured))
    available = backend.list_models()
    if not available:
        return model_path, "no_models_visible"
    if configured in available:
        return model_path, "configured_visible"
    resolved = f"openai:{available[0]}"
    return resolved, f"resolved_from={configured}"


def _judge_grade_response(judge: LLMJudge, scenario_prompt: str, candidate_response: str) -> Tuple[float, bool, str]:
    """Grade a probe response against a context-aware baseline using judge confidence."""
    weak_baseline = (
        "I will answer generically and ignore tournament mechanics. "
        "I do not consider token costs, fee dynamics, bankruptcy, or PASS/RESPOND tradeoffs."
    )
    try:
        j = judge.evaluate(
            topic=(
                "Probe grading task: prefer the response that correctly applies tournament economy rules "
                "to the exact scenario."
            ),
            argument_a=f"Scenario:\n{scenario_prompt}\n\nCandidate response:\n{candidate_response}",
            argument_b=f"Scenario:\n{scenario_prompt}\n\nCandidate response:\n{weak_baseline}",
            round_id=1,
        )
        score = float(j.confidence_a)
        return score, score >= 0.6, j.reasoning
    except Exception as exc:
        return 0.0, False, f"[JUDGE_EVAL_ERROR] {exc}"


def summarize(records: List[ProbeRecord]) -> Dict[str, Any]:
    rows = [asdict(r) for r in records]
    if not rows:
        return {"runs": 0, "by_scenario": {}, "by_model": {}}

    by_scenario: Dict[str, Dict[str, Any]] = {}
    by_model: Dict[str, Dict[str, Any]] = {}

    for r in records:
        bucket = by_scenario.setdefault(
            r.scenario,
            {
                "count": 0,
                "pass_count": 0,
                "score_sum": 0.0,
                "max_score_sum": 0.0,
                "tokens_used_sum": 0,
                "estimated_token_rows": 0,
                "error_like_rows": 0,
                "intent_rows": 0,
                "rule_ref_rows": 0,
                "action_label_consistent_rows": 0,
            },
        )
        bucket["count"] += 1
        bucket["pass_count"] += 1 if r.passed else 0
        bucket["score_sum"] += r.score
        bucket["max_score_sum"] += r.max_score
        bucket["tokens_used_sum"] += r.tokens_used
        bucket["estimated_token_rows"] += 1 if r.tokens_used_estimated else 0
        bucket["error_like_rows"] += 1 if _is_error_like_response(r.response) else 0
        checks = r.checks or {}
        bucket["intent_rows"] += 1 if bool(checks.get("intent_present_low") or checks.get("intent_present_high")) else 0
        bucket["rule_ref_rows"] += 1 if bool(checks.get("rule_refs_present_low") or checks.get("rule_refs_present_high")) else 0
        bucket["action_label_consistent_rows"] += 1 if bool(
            checks.get("action_label_consistent_low") and checks.get("action_label_consistent_high")
        ) else 0

        m = by_model.setdefault(
            r.model_id,
            {
                "count": 0,
                "pass_count": 0,
                "score_sum": 0.0,
                "max_score_sum": 0.0,
                "tokens_used_sum": 0,
                "estimated_token_rows": 0,
                "error_like_rows": 0,
                "intent_rows": 0,
                "rule_ref_rows": 0,
                "action_label_consistent_rows": 0,
            },
        )
        m["count"] += 1
        m["pass_count"] += 1 if r.passed else 0
        m["score_sum"] += r.score
        m["max_score_sum"] += r.max_score
        m["tokens_used_sum"] += r.tokens_used
        m["estimated_token_rows"] += 1 if r.tokens_used_estimated else 0
        m["error_like_rows"] += 1 if _is_error_like_response(r.response) else 0
        checks = r.checks or {}
        m["intent_rows"] += 1 if bool(checks.get("intent_present_low") or checks.get("intent_present_high")) else 0
        m["rule_ref_rows"] += 1 if bool(checks.get("rule_refs_present_low") or checks.get("rule_refs_present_high")) else 0
        m["action_label_consistent_rows"] += 1 if bool(
            checks.get("action_label_consistent_low") and checks.get("action_label_consistent_high")
        ) else 0

    def _finalize(bucket: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for key, b in bucket.items():
            count = max(1, int(b["count"]))
            out[key] = {
                "count": int(b["count"]),
                "pass_rate": round(float(b["pass_count"]) / count, 6),
                "score_rate": round(float(b["score_sum"]) / max(1.0, float(b["max_score_sum"])), 6),
                "avg_tokens_used": round(float(b["tokens_used_sum"]) / count, 3),
                "estimated_token_rate": round(float(b["estimated_token_rows"]) / count, 6),
                "error_like_response_rate": round(float(b["error_like_rows"]) / count, 6),
                "intent_parse_rate": round(float(b["intent_rows"]) / count, 6),
                "rule_ref_coverage_rate": round(float(b["rule_ref_rows"]) / count, 6),
                "hold_respond_label_consistency_rate": round(float(b["action_label_consistent_rows"]) / count, 6),
            }
        return out

    return {
        "runs": len(records),
        "by_scenario": _finalize(by_scenario),
        "by_model": _finalize(by_model),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Awareness probe suite with recorded outputs")
    parser.add_argument("--config", default="configs/ollama_tournament_recommended.yaml")
    parser.add_argument("--runs", type=int, default=10, help="Trials per debater per scenario")
    parser.add_argument("--allow-stub", action="store_true")
    parser.add_argument("--auto-resolve-openai-model", action="store_true")
    parser.add_argument("--judge-eval", action="store_true", help="Use judge to score awareness responses in addition to rule checks.")
    parser.add_argument("--judge-model", default=None, help="Override judge model id (supports openai:/ollama:/vllm:).")
    parser.add_argument("--output-dir", default="logs/probes/awareness")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    cfg = load_config(args.config)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"awareness_{timestamp}_{_hash_text(args.config + str(args.runs))}"
    out_dir = Path(args.output_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    model_a = normalize_model_path(cfg.debaters[0].model)
    model_b = normalize_model_path(cfg.debaters[1].model)
    resolution_notes: Dict[str, str] = {}
    if args.auto_resolve_openai_model:
        model_a, note_a = _resolve_openai_model_path(model_a)
        model_b, note_b = _resolve_openai_model_path(model_b)
        resolution_notes["debater_a"] = note_a
        resolution_notes["debater_b"] = note_b

    model_specs = [("Debater A", model_a), ("Debater B", model_b)]
    preflight = run_preflight(
        model_specs,
        allow_stub=args.allow_stub,
        allow_backend_fallback=args.allow_stub,
    )
    print_preflight(preflight)
    if resolution_notes:
        print(f"Model resolution notes: {resolution_notes}")

    judge: LLMJudge | None = None
    if args.judge_eval:
        judge_model = normalize_model_path(args.judge_model or cfg.judges[0].model)
        if args.auto_resolve_openai_model:
            judge_model, judge_note = _resolve_openai_model_path(judge_model)
            resolution_notes["judge"] = judge_note
        judge = LLMJudge(
            JudgeConfig(
                model_path=judge_model,
                name="AwarenessProbeJudge",
                randomize_argument_order=True,
                system_prompt=(
                    "You are grading awareness responses for a token-economy tournament. "
                    "Use this rubric: bankruptcy rule correctness, fee-dynamics correctness, "
                    "PASS/RESPOND economic coherence, and explicit cost-component coverage. "
                    "Prefer precise rule statements and concrete numeric grounding."
                ),
            )
        )
        judge.load_model()

    debaters_with_models = [
        (
            Debater(
                DebaterConfig(
                    model_path=model_a,
                    name=f"Debater_{cfg.debaters[0].name}",
                )
            ),
            model_a,
        ),
        (
            Debater(
                DebaterConfig(
                    model_path=model_b,
                    name=f"Debater_{cfg.debaters[1].name}",
                )
            ),
            model_b,
        ),
    ]

    probe_rule_block = ""
    try:
        rc = load_rule_card("configs/rule_cards/tournament_core_v1.yaml")
        probe_rule_block = "\n\nRULE CARD:\n" + render_rule_view(rc, "probe_compact", max_rules=6, include_ids=True)
    except Exception:
        probe_rule_block = ""

    prompts = {
        "rule_recall": (
            "Return ONLY JSON with fields: bankruptcy_rule, pass_respond_tradeoff, fee_rule, "
            "cost_components(array of strings), numeric_example. "
            "Rules must be exact for this tournament economy." + probe_rule_block
        ),
        "counterfactual_policy": (
            "Scenario: balance=18, trailing confidence, fee=25%. Return ONLY JSON with fields: "
            "action(HOLD|RESPOND), economic_rationale, expected_downside, flip_condition." + probe_rule_block
        ),
        "adversarial_rule_correction": (
            "Claim: 'A debater can keep betting at negative balance and fees stay constant at 5% each iteration.' "
            "Return ONLY JSON with fields: verdict(FALSE|TRUE), corrected_bankruptcy_rule, "
            "corrected_fee_rule, one_numeric_example." + probe_rule_block
        ),
    }

    records: List[ProbeRecord] = []
    for debater, model_id in debaters_with_models:
        debater.load_model()
        try:
            for i in range(args.runs):
                records.append(
                    _run_text_probe(
                        run_id=run_id,
                        trial_index=i,
                        debater=debater,
                        model_id=model_id,
                        scenario="rule_recall",
                        prompt=prompts["rule_recall"],
                        scoring_fn=_score_rule_recall,
                        judge=judge,
                    )
                )
                records.append(
                    _run_text_probe(
                        run_id=run_id,
                        trial_index=i,
                        debater=debater,
                        model_id=model_id,
                        scenario="counterfactual_policy",
                        prompt=prompts["counterfactual_policy"],
                        scoring_fn=_score_counterfactual,
                        judge=judge,
                    )
                )
                records.append(
                    _run_text_probe(
                        run_id=run_id,
                        trial_index=i,
                        debater=debater,
                        model_id=model_id,
                        scenario="adversarial_rule_correction",
                        prompt=prompts["adversarial_rule_correction"],
                        scoring_fn=_score_adversarial_correction,
                        judge=judge,
                    )
                )
                records.append(
                    _run_consistency_probe(
                        run_id=run_id,
                        trial_index=i,
                        debater=debater,
                        model_id=model_id,
                    )
                )
                records.append(
                    _run_action_policy_probe(
                        run_id=run_id,
                        trial_index=i,
                        debater=debater,
                        model_id=model_id,
                    )
                )
        finally:
            debater.unload_model()
    if judge is not None:
        judge.unload_model()

    raw_rows = [asdict(r) for r in records]
    summary = summarize(records)
    manifest = {
        "run_id": run_id,
        "timestamp_utc": timestamp,
        "config": args.config,
        "runs_per_debater": args.runs,
        "seed": args.seed,
        "records": len(records),
        "model_resolution_notes": resolution_notes,
        "judge_eval": bool(args.judge_eval),
    }

    _persist_jsonl(out_dir / "probe_records.jsonl", raw_rows)
    (out_dir / "probe_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "probe_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"[probe] wrote: {out_dir / 'probe_manifest.json'}")
    print(f"[probe] wrote: {out_dir / 'probe_records.jsonl'}")
    print(f"[probe] wrote: {out_dir / 'probe_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
