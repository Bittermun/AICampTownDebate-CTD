import re
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.arena.dynamic_round import DynamicDebateRound, DynamicRoundContext
from src.economy import BettingManager, TokenDistributor, TokenLedger
from src.logs.transcript import RoundTranscript
from src.models import BetDecision, BetType, Debater, DebaterConfig
from src.models.judge import JudgeConfig, Judgment, LLMJudge


def _build_rounder() -> tuple[DynamicDebateRound, TokenLedger]:
    ledger = TokenLedger(initial_balance=100.0, max_debt=50.0)
    ledger.register("A")
    ledger.register("B")
    betting = BettingManager(fee_rate=0.05, min_bet=5.0)
    distributor = TokenDistributor(tokens_per_round=20.0)
    debater_a = Debater(DebaterConfig(model_path="stub", name="A", strict_runtime=False))
    debater_b = Debater(DebaterConfig(model_path="stub", name="B", strict_runtime=False))
    judge = LLMJudge(JudgeConfig(model_path="stub", name="J", strict_runtime=False))
    rounder = DynamicDebateRound(
        debater_a=debater_a,
        debater_b=debater_b,
        judge=judge,
        ledger=ledger,
        betting=betting,
        distributor=distributor,
        max_iterations=1,
    )
    return rounder, ledger


def _base_ctx(ledger: TokenLedger) -> DynamicRoundContext:
    ctx = DynamicRoundContext(round_id=1, topic="t", debater_a_id="A", debater_b_id="B", ledger=ledger)
    ctx.initial_judgment = Judgment(confidence_a=0.4, confidence_b=0.6, reasoning="init", judge_id="J", round_id=1)
    ctx.current_judgment = Judgment(confidence_a=0.7, confidence_b=0.3, reasoning="final", judge_id="J", round_id=1)
    return ctx


def test_bet_resolution_not_transcript_dependent() -> None:
    rounder, ledger = _build_rounder()
    ctx = _base_ctx(ledger)
    bet = rounder.betting.place_bet("A", amount=10.0, round_id=1, ledger=ledger)
    assert bet is not None
    ctx.all_bets.append(bet)
    ctx.locked_pot += bet.amount

    rounder._phase_distribute_tokens(ctx, transcript=None)
    assert bet.status.value != "pending"
    assert bet.payout > 0.0


def test_invalid_respond_decision_is_normalized_to_hold() -> None:
    rounder, _ledger = _build_rounder()
    decision = BetDecision(
        bet_type=BetType.RESPOND,
        amount=1.0,
        reasoning="Try tiny respond",
        llm_tokens_used=12,
        max_budget=10.0,
    )
    normalized = rounder._normalize_response_decision(
        decision=decision,
        debater_id="A",
        balance=100.0,
        current_fee_rate=0.05,
    )
    assert normalized.bet_type == BetType.PASS
    assert normalized.amount == 0.0
    assert normalized.action_label == "HOLD"
    assert "[BET_REJECTED_MIN]" in normalized.reasoning


def test_transcript_bet_payout_matches_resolved_payout() -> None:
    rounder, ledger = _build_rounder()
    ctx = _base_ctx(ledger)
    bet = rounder.betting.place_bet("A", amount=10.0, round_id=1, ledger=ledger)
    assert bet is not None
    ctx.all_bets.append(bet)
    ctx.locked_pot += bet.amount

    transcript = RoundTranscript(round_id=1, topic="t")
    rounder._phase_distribute_tokens(ctx, transcript=transcript)

    payout_lines = [t.content for t in transcript.turns if t.turn_type == "payout" and "Bet Outcome" in t.content]
    assert payout_lines, "Expected transcript payout line for resolved bet."
    m = re.search(r"\*\*Payout\*\*:\s*([+-]?[0-9]+(?:\.[0-9]+)?)", payout_lines[0])
    assert m is not None
    transcript_payout = float(m.group(1))
    assert abs(transcript_payout - round(bet.payout, 1)) < 1e-6


if __name__ == "__main__":
    test_bet_resolution_not_transcript_dependent()
    test_invalid_respond_decision_is_normalized_to_hold()
    test_transcript_bet_payout_matches_resolved_payout()
    print("test_econ_invariants: PASS")
