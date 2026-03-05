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


def test_ledger_rejects_non_positive_deduct_amount() -> None:
    ledger = TokenLedger(initial_balance=50.0, max_debt=0.0)
    ledger.register("A")
    before = ledger.balance("A")

    assert ledger.deduct("A", 0.0, "noop", 1) is False
    assert ledger.deduct("A", -1.0, "negative", 1) is False
    assert ledger.balance("A") == before


def test_place_bet_rejects_invalid_custom_fee_rate() -> None:
    ledger = TokenLedger(initial_balance=100.0, max_debt=0.0)
    ledger.register("A")
    betting = BettingManager(fee_rate=0.05, min_bet=5.0)

    assert betting.place_bet("A", 10.0, 1, ledger, custom_fee_rate=-0.1) is None
    assert betting.place_bet("A", 10.0, 1, ledger, custom_fee_rate=1.1) is None
    assert ledger.balance("A") == 100.0


def test_place_bet_refunds_when_fee_deduct_fails() -> None:
    ledger = TokenLedger(initial_balance=100.0, max_debt=0.0)
    ledger.register("A")
    betting = BettingManager(fee_rate=0.05, min_bet=5.0)
    real_deduct = ledger.deduct

    def _flaky_deduct(agent_id: str, amount: float, reason: str, round_id: int) -> bool:
        if reason == "bet_fee":
            return False
        return real_deduct(agent_id, amount, reason, round_id)

    ledger.deduct = _flaky_deduct  # type: ignore[assignment]
    bet = betting.place_bet("A", 10.0, 1, ledger)
    assert bet is None
    assert ledger.balance("A") == 100.0


def test_dynamic_round_result_carries_accounting_fields() -> None:
    rounder, ledger = _build_rounder()
    ctx = _base_ctx(ledger)
    ctx.round_supply_start = sum(ledger.summary()["balances"].values())
    rounder._phase_distribute_tokens(ctx, transcript=None)
    rounder._audit_round_accounting(ctx)

    result = rounder._build_result(ctx, observation_reports=[])
    assert isinstance(result.accounting_ok, bool)
    assert isinstance(result.accounting_notes, list)
    assert result.round_supply_end >= result.round_supply_start


if __name__ == "__main__":
    test_bet_resolution_not_transcript_dependent()
    test_invalid_respond_decision_is_normalized_to_hold()
    test_transcript_bet_payout_matches_resolved_payout()
    print("test_econ_invariants: PASS")
