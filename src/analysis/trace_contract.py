"""Canonical trace contract for downstream memory and training consumers."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import re


_DECISION_RE = re.compile(r"\*\*Decision\*\*:\s*([A-Za-z_]+)")
_INTENT_RE = re.compile(r"\*\*Intent\*\*:\s*([^\|\n]+)")
_REASONING_RE = re.compile(r"\*\*Reasoning\*\*:\s*(.*)", re.DOTALL)
_BALANCE_RE = re.compile(r"\*\*Balance\*\*:\s*([-+]?\d+(?:\.\d+)?)")
_STANDING_RE = re.compile(r"\*\*Standing\*\*:\s*([-+]?\d+(?:\.\d+)?)%\s*vs\s*([-+]?\d+(?:\.\d+)?)%")
_ITER_RE = re.compile(r"\[Iter\s+(\d+)\]", re.IGNORECASE)
_INTENT_MIX_RE = re.compile(r"\*\*Intent Mix\*\*:\s*(\[.*\])")


@dataclass
class TraceRecord:
    """Normalized per-decision trace entry."""

    trace_id: str
    run_id: str
    seed: Optional[int]
    round_id: int
    iteration: int
    speaker: str
    decision: str
    reasoning: str
    intent: str
    intent_mix: Optional[List[Dict[str, Any]]]
    balance: Optional[float]
    confidence_self: Optional[float]
    confidence_opponent: Optional[float]
    tokens_bet: float
    llm_tokens_used: Optional[int]
    outcome_delta: Optional[float]
    source_ref: str
    judge_model: str
    judge_reliability_tier: str
    provenance_source: str = "raw_transcript"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _parse_float(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_int(raw: Optional[str]) -> Optional[int]:
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def assign_trace_quality_tier(run_metadata: Dict[str, Any], gate_summary: Dict[str, Any]) -> str:
    """
    Assign trace trust tier from run metadata and gate outcomes.

    Tiers:
    - tier_a: judge variance and calibration both explicitly pass
    - tier_b: no explicit judge failure, but reliability is partial/unknown
    - tier_c: explicit judge reliability failure or failed run
    """
    _ = run_metadata  # Reserved for future policy-driven tier controls.

    def _as_optional_bool(value: Any) -> Optional[bool]:
        if isinstance(value, bool):
            return value
        return None

    judge_variance_pass = _as_optional_bool(gate_summary.get("judge_variance_pass"))
    judge_calibration_pass = _as_optional_bool(gate_summary.get("judge_calibration_pass"))

    # Explicit failure always downgrades to tier_c.
    if judge_variance_pass is False or judge_calibration_pass is False:
        return "tier_c"

    # High-trust traces require both reliability gates to explicitly pass.
    if judge_variance_pass is True and judge_calibration_pass is True:
        return "tier_a"

    # Otherwise, unresolved/disabled reliability gates can still produce
    # tier_b traces if the run itself passed.
    gates_pass = bool(gate_summary.get("gates_pass", False))
    if gates_pass:
        return "tier_b"
    return "tier_c"


def normalize_transcript_to_traces(
    transcript: Dict[str, Any],
    ledger: Optional[Dict[str, Any]] = None,
    *,
    run_id: Optional[str] = None,
    seed: Optional[int] = None,
    judge_model: Optional[str] = None,
    judge_reliability_tier: str = "tier_b",
) -> List[TraceRecord]:
    """
    Convert transcript rounds/turns into canonical decision traces.

    The function is intentionally conservative: it emits one record per
    deliberation turn with a parseable decision.
    """
    _ = ledger  # Reserved for future delta derivation.
    traces: List[TraceRecord] = []
    run_label = run_id or str(transcript.get("tournament_id", "unknown_run"))
    config = transcript.get("config", {}) or {}
    judge_name = judge_model or str(config.get("judge", "unknown_judge"))

    for round_obj in transcript.get("rounds", []):
        round_id = int(round_obj.get("round_id", 0) or 0)
        conf_a = _parse_float(str(round_obj.get("confidence_a"))) if round_obj.get("confidence_a") is not None else None
        conf_b = _parse_float(str(round_obj.get("confidence_b"))) if round_obj.get("confidence_b") is not None else None
        tokens_a = _parse_float(str(round_obj.get("tokens_awarded_a"))) if round_obj.get("tokens_awarded_a") is not None else None
        tokens_b = _parse_float(str(round_obj.get("tokens_awarded_b"))) if round_obj.get("tokens_awarded_b") is not None else None

        # Infer A/B speaker mapping from first two argument turns.
        turns = round_obj.get("turns", []) or []
        arg_speakers = [t.get("speaker", "") for t in turns if t.get("type") == "argument"]
        speaker_a = arg_speakers[0] if len(arg_speakers) >= 1 else None
        speaker_b = arg_speakers[1] if len(arg_speakers) >= 2 else None

        for turn_idx, turn in enumerate(turns):
            if turn.get("type") != "deliberation":
                continue

            content = str(turn.get("content", ""))
            decision_match = _DECISION_RE.search(content)
            if not decision_match:
                continue
            decision = decision_match.group(1).upper()
            intent_match = _INTENT_RE.search(content)
            reasoning_match = _REASONING_RE.search(content)
            balance_match = _BALANCE_RE.search(content)
            standing_match = _STANDING_RE.search(content)
            iter_match = _ITER_RE.search(content)
            intent_mix_match = _INTENT_MIX_RE.search(content)

            intent = (intent_match.group(1).strip().lower() if intent_match else "other")
            reasoning = reasoning_match.group(1).strip() if reasoning_match else ""
            iteration = _parse_int(iter_match.group(1) if iter_match else None) or 0
            balance = _parse_float(balance_match.group(1) if balance_match else None)

            confidence_self: Optional[float] = None
            confidence_opp: Optional[float] = None
            if standing_match:
                # Standing percentages are emitted as [0, 100], convert to [0, 1].
                confidence_self = (_parse_float(standing_match.group(1)) or 0.0) / 100.0
                confidence_opp = (_parse_float(standing_match.group(2)) or 0.0) / 100.0
            elif speaker_a and turn.get("speaker") == speaker_a and conf_a is not None and conf_b is not None:
                confidence_self, confidence_opp = conf_a, conf_b
            elif speaker_b and turn.get("speaker") == speaker_b and conf_a is not None and conf_b is not None:
                confidence_self, confidence_opp = conf_b, conf_a

            outcome_delta: Optional[float] = None
            if speaker_a and turn.get("speaker") == speaker_a:
                outcome_delta = tokens_a
            elif speaker_b and turn.get("speaker") == speaker_b:
                outcome_delta = tokens_b

            intent_mix = None
            if intent_mix_match:
                try:
                    parsed = json.loads(intent_mix_match.group(1))
                    if isinstance(parsed, list):
                        intent_mix = parsed
                except json.JSONDecodeError:
                    intent_mix = None

            source_ref = f"round:{round_id}:turn:{turn_idx}"
            trace_id = f"{run_label}:r{round_id}:t{turn_idx}"
            traces.append(
                TraceRecord(
                    trace_id=trace_id,
                    run_id=run_label,
                    seed=seed,
                    round_id=round_id,
                    iteration=iteration,
                    speaker=str(turn.get("speaker", "unknown")),
                    decision=decision,
                    reasoning=reasoning,
                    intent=intent,
                    intent_mix=intent_mix,
                    balance=balance,
                    confidence_self=confidence_self,
                    confidence_opponent=confidence_opp,
                    tokens_bet=float(turn.get("tokens_bet", 0.0) or 0.0),
                    llm_tokens_used=None,
                    outcome_delta=outcome_delta,
                    source_ref=source_ref,
                    judge_model=judge_name,
                    judge_reliability_tier=judge_reliability_tier,
                )
            )
    return traces


def export_trace_jsonl(traces: List[TraceRecord], path: str) -> None:
    """Persist normalized traces as JSONL."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(t.to_dict(), sort_keys=True) for t in traces)
    if payload:
        payload += "\n"
    out_path.write_text(payload, encoding="utf-8")
