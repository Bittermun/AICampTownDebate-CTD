import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.reconcile_settlement import reconcile


def test_reconcile_sets_quality_blocker_on_bet_mismatch(tmp_path: Path) -> None:
    transcript = {
        "config": {"debater_a": "A", "debater_b": "B"},
        "rounds": [
            {
                "round_id": 1,
                "tokens_awarded_a": 10.0,
                "tokens_awarded_b": 10.0,
                "turns": [
                    {
                        "type": "payout",
                        "speaker": "A",
                        "content": "Bet Outcome **Payout**: 5.0",
                    }
                ],
            }
        ],
    }
    ledger = {
        "transactions": [
            {"round": 1, "to": "A", "amount": 0.0, "reason": "bet_won:1"},
            {"round": 1, "to": "A", "amount": 10.0, "reason": "pot_split"},
            {"round": 1, "to": "B", "amount": 10.0, "reason": "pot_split"},
        ]
    }

    tp = tmp_path / "transcript.json"
    lp = tmp_path / "ledger.json"
    tp.write_text(json.dumps(transcript), encoding="utf-8")
    lp.write_text(json.dumps(ledger), encoding="utf-8")

    report = reconcile(str(tp), str(lp))
    assert report["ok"] is False
    assert report["quality_claim_blocked"] is True
    assert "bet_payout_mismatches=1" in report["blocker_reasons"]


def test_reconcile_blocks_empty_transcript(tmp_path: Path) -> None:
    tp = tmp_path / "transcript.json"
    lp = tmp_path / "ledger.json"
    tp.write_text(
        json.dumps({"config": {"debater_a": "A", "debater_b": "B"}, "rounds": []}),
        encoding="utf-8",
    )
    lp.write_text(json.dumps({"transactions": [{"round": 0, "to": "A", "amount": 1.0, "reason": "initial_balance"}]}), encoding="utf-8")

    report = reconcile(str(tp), str(lp))
    assert report["ok"] is False
    assert any("no rounds" in x for x in report["blocker_reasons"])


def test_reconcile_flags_pending_bets_from_results(tmp_path: Path) -> None:
    transcript = {
        "config": {"debater_a": "A", "debater_b": "B"},
        "rounds": [
            {
                "round_id": 1,
                "tokens_awarded_a": 10.0,
                "tokens_awarded_b": 10.0,
                "turns": [],
            }
        ],
    }
    ledger = {
        "transactions": [
            {"round": 1, "to": "A", "amount": 10.0, "reason": "pot_split"},
            {"round": 1, "to": "B", "amount": 10.0, "reason": "pot_split"},
        ]
    }
    results = {
        "rounds": [
            {
                "round_id": 1,
                "bets": 1,
                "bet_status_counts": {"pending": 1, "won": 0, "lost": 0, "cancelled": 0},
                "bets_pending": 1,
            }
        ]
    }

    tp = tmp_path / "transcript.json"
    lp = tmp_path / "ledger.json"
    rp = tmp_path / "results.json"
    tp.write_text(json.dumps(transcript), encoding="utf-8")
    lp.write_text(json.dumps(ledger), encoding="utf-8")
    rp.write_text(json.dumps(results), encoding="utf-8")

    report = reconcile(str(tp), str(lp), results_path=str(rp))
    assert report["ok"] is False
    assert report["pending_bet_round_count"] == 1
    assert "pending_bet_rounds=1" in report["blocker_reasons"]
