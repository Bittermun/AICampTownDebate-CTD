#!/usr/bin/env python3
"""Reconcile settlement signals between transcript and ledger artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Dict, Tuple


PAYOUT_RE = re.compile(r"\*\*Payout\*\*:\s*([+-]?[0-9]+(?:\.[0-9]+)?)")


def _round_speaker_map(transcript_obj: dict) -> Tuple[str, str]:
    cfg = transcript_obj.get("config", {})
    a = str(cfg.get("debater_a", "Debater_A"))
    b = str(cfg.get("debater_b", "Debater_B"))
    return a, b


def _transcript_bet_payouts(transcript_obj: dict) -> Dict[int, Dict[str, float]]:
    out: Dict[int, Dict[str, float]] = {}
    for rnd in transcript_obj.get("rounds", []):
        rid = int(rnd.get("round_id", 0))
        bucket: Dict[str, float] = {}
        for turn in rnd.get("turns", []):
            if turn.get("type") != "payout":
                continue
            content = str(turn.get("content", ""))
            if "Bet Outcome" not in content:
                continue
            m = PAYOUT_RE.search(content)
            if not m:
                continue
            speaker = str(turn.get("speaker", ""))
            bucket[speaker] = bucket.get(speaker, 0.0) + float(m.group(1))
        out[rid] = bucket
    return out


def _ledger_amounts(ledger_obj: dict, reason_prefix: str) -> Dict[int, Dict[str, float]]:
    out: Dict[int, Dict[str, float]] = {}
    for tx in ledger_obj.get("transactions", []):
        reason = str(tx.get("reason", ""))
        if not reason.startswith(reason_prefix):
            continue
        rid = int(tx.get("round", 0))
        to_id = str(tx.get("to", ""))
        if not to_id:
            continue
        by_round = out.setdefault(rid, {})
        by_round[to_id] = by_round.get(to_id, 0.0) + float(tx.get("amount", 0.0))
    return out


def _ledger_awards(ledger_obj: dict, allowed_reasons: set[str]) -> Dict[int, Dict[str, float]]:
    out: Dict[int, Dict[str, float]] = {}
    for tx in ledger_obj.get("transactions", []):
        if str(tx.get("reason", "")) not in allowed_reasons:
            continue
        rid = int(tx.get("round", 0))
        to_id = str(tx.get("to", ""))
        if not to_id:
            continue
        by_round = out.setdefault(rid, {})
        by_round[to_id] = by_round.get(to_id, 0.0) + float(tx.get("amount", 0.0))
    return out


def reconcile(transcript_path: str, ledger_path: str, tolerance: float = 1e-6) -> dict:
    transcript_obj = json.loads(Path(transcript_path).read_text(encoding="utf-8"))
    ledger_obj = json.loads(Path(ledger_path).read_text(encoding="utf-8"))

    debater_a, debater_b = _round_speaker_map(transcript_obj)
    tx_bet = _transcript_bet_payouts(transcript_obj)
    ld_bet = _ledger_amounts(ledger_obj, "bet_won:")
    ld_round_awards = _ledger_awards(ledger_obj, {"pot_split", "initial_bounty"})

    rounds = sorted({int(r.get("round_id", 0)) for r in transcript_obj.get("rounds", [])})
    bet_mismatches = []
    pot_mismatches = []

    for rid in rounds:
        tx_round = tx_bet.get(rid, {})
        ld_round = ld_bet.get(rid, {})
        speakers = sorted(set(tx_round.keys()) | set(ld_round.keys()))
        for speaker in speakers:
            tx_amt = float(tx_round.get(speaker, 0.0))
            ld_amt = float(ld_round.get(speaker, 0.0))
            # Transcript payout lines are formatted to 1 decimal place.
            ld_amt_view = round(ld_amt, 1)
            if abs(tx_amt - ld_amt_view) > tolerance:
                bet_mismatches.append(
                    {
                        "round_id": rid,
                        "speaker": speaker,
                        "transcript_bet_payout": tx_amt,
                        "ledger_bet_won_sum": ld_amt,
                        "ledger_bet_won_rounded_1dp": ld_amt_view,
                        "delta": tx_amt - ld_amt_view,
                    }
                )

        # Pot split reconciliation against round-level transcript awarded fields.
        round_obj = next((r for r in transcript_obj.get("rounds", []) if int(r.get("round_id", 0)) == rid), None)
        if round_obj is None:
            continue
        tx_award_a = float(round_obj.get("tokens_awarded_a", 0.0))
        tx_award_b = float(round_obj.get("tokens_awarded_b", 0.0))
        ld_award_a = float(ld_round_awards.get(rid, {}).get(debater_a, 0.0))
        ld_award_b = float(ld_round_awards.get(rid, {}).get(debater_b, 0.0))

        if abs(tx_award_a - ld_award_a) > tolerance:
            pot_mismatches.append(
                {
                    "round_id": rid,
                    "speaker": debater_a,
                    "transcript_tokens_awarded": tx_award_a,
                    "ledger_pot_split_sum": ld_award_a,
                    "delta": tx_award_a - ld_award_a,
                }
            )
        if abs(tx_award_b - ld_award_b) > tolerance:
            pot_mismatches.append(
                {
                    "round_id": rid,
                    "speaker": debater_b,
                    "transcript_tokens_awarded": tx_award_b,
                    "ledger_pot_split_sum": ld_award_b,
                    "delta": tx_award_b - ld_award_b,
                }
            )

    ok = not bet_mismatches and not pot_mismatches
    return {
        "transcript_path": transcript_path,
        "ledger_path": ledger_path,
        "ok": ok,
        "round_count": len(rounds),
        "bet_mismatch_count": len(bet_mismatches),
        "pot_split_mismatch_count": len(pot_mismatches),
        "bet_mismatches": bet_mismatches,
        "pot_split_mismatches": pot_mismatches,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile transcript and ledger settlement signals")
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument("--tolerance", type=float, default=1e-6)
    args = parser.parse_args()

    report = reconcile(args.transcript, args.ledger, tolerance=args.tolerance)
    print(json.dumps(report, indent=2))

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"[reconcile] wrote: {out}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
