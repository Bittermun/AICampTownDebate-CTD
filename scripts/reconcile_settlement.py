#!/usr/bin/env python3
"""Reconcile settlement signals between transcript, ledger, and optional results artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple


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


def _transcript_bet_outcome_counts(transcript_obj: dict) -> Dict[int, int]:
    counts: Dict[int, int] = {}
    for rnd in transcript_obj.get("rounds", []):
        rid = int(rnd.get("round_id", 0))
        total = 0
        for turn in rnd.get("turns", []):
            if turn.get("type") != "payout":
                continue
            content = str(turn.get("content", ""))
            if "Bet Outcome" in content:
                total += 1
        counts[rid] = total
    return counts


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


def _extract_pending_bets(results_obj: Optional[dict]) -> List[dict]:
    if not isinstance(results_obj, dict):
        return []

    unresolved: List[dict] = []
    rounds = results_obj.get("rounds", [])
    if not isinstance(rounds, list):
        return unresolved

    for rnd in rounds:
        if not isinstance(rnd, dict):
            continue
        rid = int(rnd.get("round_id", 0))
        pending = None
        if "bets_pending" in rnd:
            try:
                pending = int(rnd.get("bets_pending", 0))
            except Exception:
                pending = None
        if pending is None:
            status_counts = rnd.get("bet_status_counts", {})
            if isinstance(status_counts, dict):
                try:
                    pending = int(status_counts.get("pending", 0))
                except Exception:
                    pending = None
        if pending and pending > 0:
            unresolved.append({"round_id": rid, "pending_bets": pending})

    return unresolved


def reconcile(
    transcript_path: str,
    ledger_path: str,
    results_path: Optional[str] = None,
    tolerance: float = 1e-6,
) -> dict:
    transcript_obj = json.loads(Path(transcript_path).read_text(encoding="utf-8"))
    ledger_obj = json.loads(Path(ledger_path).read_text(encoding="utf-8"))
    results_obj = None
    if results_path:
        rp = Path(results_path)
        if rp.exists():
            results_obj = json.loads(rp.read_text(encoding="utf-8"))

    debater_a, debater_b = _round_speaker_map(transcript_obj)
    tx_bet = _transcript_bet_payouts(transcript_obj)
    tx_bet_outcomes = _transcript_bet_outcome_counts(transcript_obj)
    ld_bet = _ledger_amounts(ledger_obj, "bet_won:")
    ld_round_awards = _ledger_awards(ledger_obj, {"pot_split", "initial_bounty"})
    unresolved_pending_bets = _extract_pending_bets(results_obj)

    rounds = sorted({int(r.get("round_id", 0)) for r in transcript_obj.get("rounds", [])})
    structure_issues = []
    if not rounds:
        structure_issues.append("transcript has no rounds")
    ledger_txs = ledger_obj.get("transactions", [])
    if not isinstance(ledger_txs, list):
        structure_issues.append("ledger.transactions missing or invalid")
        ledger_txs = []
    elif len(ledger_txs) == 0:
        structure_issues.append("ledger has no transactions")
    bet_mismatches = []
    pot_mismatches = []
    settlement_count_mismatches = []

    for rid in rounds:
        tx_round = tx_bet.get(rid, {})
        ld_round = ld_bet.get(rid, {})
        speakers = sorted(set(tx_round.keys()) | set(ld_round.keys()))
        for speaker in speakers:
            tx_amt = float(tx_round.get(speaker, 0.0))
            ld_amt = float(ld_round.get(speaker, 0.0))
            if abs(tx_amt - ld_amt) > tolerance:
                bet_mismatches.append(
                    {
                        "round_id": rid,
                        "speaker": speaker,
                        "transcript_bet_payout": tx_amt,
                        "ledger_bet_won_sum": ld_amt,
                        "delta": tx_amt - ld_amt,
                    }
                )

        transcript_count = int(tx_bet_outcomes.get(rid, 0))
        ledger_count = len(ld_round)
        if transcript_count != ledger_count:
            settlement_count_mismatches.append(
                {
                    "round_id": rid,
                    "transcript_bet_outcome_rows": transcript_count,
                    "ledger_bet_winner_rows": ledger_count,
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

    ok = (
        not structure_issues
        and
        not bet_mismatches
        and not pot_mismatches
        and not settlement_count_mismatches
        and not unresolved_pending_bets
    )
    blocker_reasons = list(structure_issues)
    if bet_mismatches:
        blocker_reasons.append(f"bet_payout_mismatches={len(bet_mismatches)}")
    if pot_mismatches:
        blocker_reasons.append(f"pot_split_mismatches={len(pot_mismatches)}")
    if settlement_count_mismatches:
        blocker_reasons.append(f"settlement_count_mismatches={len(settlement_count_mismatches)}")
    if unresolved_pending_bets:
        blocker_reasons.append(f"pending_bet_rounds={len(unresolved_pending_bets)}")
    return {
        "transcript_path": transcript_path,
        "ledger_path": ledger_path,
        "results_path": results_path,
        "ok": ok,
        "quality_claim_blocked": not ok,
        "blocker_reasons": blocker_reasons,
        "structure_issue_count": len(structure_issues),
        "round_count": len(rounds),
        "bet_mismatch_count": len(bet_mismatches),
        "pot_split_mismatch_count": len(pot_mismatches),
        "settlement_count_mismatch_count": len(settlement_count_mismatches),
        "pending_bet_round_count": len(unresolved_pending_bets),
        "structure_issues": structure_issues,
        "bet_mismatches": bet_mismatches,
        "pot_split_mismatches": pot_mismatches,
        "settlement_count_mismatches": settlement_count_mismatches,
        "pending_bet_rounds": unresolved_pending_bets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile transcript and ledger settlement signals")
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--results", default=None, help="Optional tournament_results.json for pending bet checks")
    parser.add_argument("--output", default=None)
    parser.add_argument("--tolerance", type=float, default=1e-6)
    args = parser.parse_args()

    report = reconcile(args.transcript, args.ledger, results_path=args.results, tolerance=args.tolerance)
    print(json.dumps(report, indent=2))

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"[reconcile] wrote: {out}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
