
from src.economy import TokenLedger, BettingManager
from src.arena.dynamic_round import DynamicDebateRound, DynamicRoundContext
from src.models import Debater, DebaterConfig, JudgeFactory
from src.economy import TokenDistributor

def test_scaling_fees():
    print("Verifying Scaling Fees in Dynamic Rounds...")
    ledger = TokenLedger(initial_balance=1000.0)
    betting = BettingManager(fee_rate=0.05)
    distributor = TokenDistributor()
    
    # Setup stub agents
    deb_a = Debater(DebaterConfig(model_path="stub", name="Alpha"))
    deb_b = Debater(DebaterConfig(model_path="stub", name="Beta"))
    judge = JudgeFactory.create_simple("stub", name="Judge")
    
    round_obj = DynamicDebateRound(deb_a, deb_b, judge, ledger, betting, distributor)
    
    # Test iteration 1 fee (should be 5%)
    print("\n--- Iteration 1 (Expect 5% Fee) ---")
    ctx = DynamicRoundContext(round_id=1, topic="Test", iteration=1)
    ledger.register("Alpha")
    
    # Simulate _process_bet logic for Alpha
    # Bet 100
    iteration_fee = min(0.05 * ctx.iteration, 0.50)
    print(f"Calculated Fee Rate: {iteration_fee:.2f}")
    
    bal_before = ledger.balance("Alpha")
    betting.place_bet("Alpha", 100, 1, ledger, custom_fee_rate=iteration_fee)
    bal_after = ledger.balance("Alpha")
    fee_paid = bal_before - bal_after - 100
    print(f"Fee Paid: {fee_paid} (Expected: 5.0)")
    
    # Test iteration 5 fee (should be 25%)
    print("\n--- Iteration 5 (Expect 25% Fee) ---")
    ctx.iteration = 5
    iteration_fee = min(0.05 * ctx.iteration, 0.50)
    print(f"Calculated Fee Rate: {iteration_fee:.2f}")
    
    bal_before = ledger.balance("Alpha")
    betting.place_bet("Alpha", 100, 1, ledger, custom_fee_rate=iteration_fee)
    bal_after = ledger.balance("Alpha")
    fee_paid = bal_before - bal_after - 100
    print(f"Fee Paid: {fee_paid} (Expected: 25.0)")

    # Test iteration 12 fee (should be capped at 50%)
    print("\n--- Iteration 12 (Expect 50% Cap) ---")
    ctx.iteration = 12
    iteration_fee = min(0.05 * ctx.iteration, 0.50)
    print(f"Calculated Fee Rate: {iteration_fee:.2f}")
    
    bal_before = ledger.balance("Alpha")
    betting.place_bet("Alpha", 100, 1, ledger, custom_fee_rate=iteration_fee)
    bal_after = ledger.balance("Alpha")
    fee_paid = bal_before - bal_after - 100
    print(f"Fee Paid: {fee_paid} (Expected: 50.0)")

if __name__ == "__main__":
    test_scaling_fees()
