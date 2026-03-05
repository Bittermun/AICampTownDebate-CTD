"""Training data contracts for post-tournament learning loops."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json


@dataclass
class SFTExample:
    prompt: str
    response: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PreferencePair:
    prompt: str
    chosen: str
    rejected: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrainingDatasetManifest:
    created_at: str
    run_ids: List[str]
    trace_paths: List[str] = field(default_factory=list)
    sft_path: Optional[str] = None
    preference_path: Optional[str] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_sft_examples_from_traces(traces: List[Dict[str, Any]]) -> List[SFTExample]:
    """Create lightweight SFT examples from normalized trace records."""
    examples: List[SFTExample] = []
    for t in traces:
        decision = str(t.get("decision", "")).upper()
        reasoning = str(t.get("reasoning", "")).strip()
        if not decision:
            continue
        prompt = (
            "Debate state:\n"
            f"- round_id: {t.get('round_id')}\n"
            f"- iteration: {t.get('iteration')}\n"
            f"- speaker: {t.get('speaker')}\n"
            f"- balance: {t.get('balance')}\n"
            f"- confidence_self: {t.get('confidence_self')}\n"
            f"- confidence_opponent: {t.get('confidence_opponent')}\n"
            "Predict an economically-rational next action."
        )
        response = json.dumps(
            {
                "decision": decision,
                "reasoning": reasoning,
                "intent": t.get("intent"),
            },
            sort_keys=True,
        )
        examples.append(
            SFTExample(
                prompt=prompt,
                response=response,
                metadata={
                    "trace_id": t.get("trace_id"),
                    "judge_reliability_tier": t.get("judge_reliability_tier"),
                    "provenance_source": t.get("provenance_source"),
                },
            )
        )
    return examples


def build_preference_pairs_from_rounds(
    summary: Dict[str, Any],
    traces: List[Dict[str, Any]],
) -> List[PreferencePair]:
    """
    Build coarse preference pairs from same-round decisions.

    Rule (skeleton): within a round, prefer traces with larger signed EV proxy:
      ev_proxy = tokens_bet * (confidence_self - confidence_opponent)
    This is a per-decision estimate and avoids using round-level payout as a
    direct label for every deliberation turn.

    Future upgrade: switch to look-ahead balance delta once iteration-level
    balance tracking is available in transcript/trace artifacts.
    """
    _ = summary  # Reserved for richer pairwise construction.

    def _safe_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _signed_ev_proxy(trace: Dict[str, Any]) -> float:
        tokens_bet = max(0.0, _safe_float(trace.get("tokens_bet", 0.0)))
        conf_self = _safe_float(trace.get("confidence_self", 0.0))
        conf_opp = _safe_float(trace.get("confidence_opponent", 0.0))
        edge = conf_self - conf_opp
        return tokens_bet * edge

    by_round: Dict[int, List[Dict[str, Any]]] = {}
    for t in traces:
        rid = int(t.get("round_id", 0) or 0)
        by_round.setdefault(rid, []).append(t)

    pairs: List[PreferencePair] = []
    for rid, bucket in by_round.items():
        if len(bucket) < 2:
            continue
        ordered = sorted(
            bucket,
            key=lambda x: (
                _signed_ev_proxy(x),
                1.0 if str(x.get("decision", "")).upper() not in {"PASS", "HOLD"} else 0.0,
            ),
            reverse=True,
        )
        best = ordered[0]
        worst = ordered[-1]
        if best is worst:
            continue
        prompt = (
            "Choose the better strategy under token constraints.\n"
            f"- round_id: {rid}\n"
            f"- best_trace_id: {best.get('trace_id')}\n"
            f"- worst_trace_id: {worst.get('trace_id')}"
        )
        chosen = json.dumps(
            {
                "decision": best.get("decision"),
                "reasoning": best.get("reasoning"),
            },
            sort_keys=True,
        )
        rejected = json.dumps(
            {
                "decision": worst.get("decision"),
                "reasoning": worst.get("reasoning"),
            },
            sort_keys=True,
        )
        pairs.append(
            PreferencePair(
                prompt=prompt,
                chosen=chosen,
                rejected=rejected,
                metadata={
                    "round_id": rid,
                    "chosen_trace_id": best.get("trace_id"),
                    "rejected_trace_id": worst.get("trace_id"),
                    "chosen_ev_proxy": round(_signed_ev_proxy(best), 6),
                    "rejected_ev_proxy": round(_signed_ev_proxy(worst), 6),
                },
            )
        )
    return pairs


def save_manifest(manifest: TrainingDatasetManifest, path: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")


def make_manifest(
    run_ids: List[str],
    trace_paths: List[str],
    sft_path: Optional[str] = None,
    preference_path: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    notes: str = "",
) -> TrainingDatasetManifest:
    return TrainingDatasetManifest(
        created_at=datetime.now(timezone.utc).isoformat(),
        run_ids=list(run_ids),
        trace_paths=list(trace_paths),
        sft_path=sft_path,
        preference_path=preference_path,
        filters=filters or {},
        notes=notes,
    )
