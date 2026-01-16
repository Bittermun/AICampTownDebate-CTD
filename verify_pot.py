
from src.economy import TokenLedger, TokenDistributor, BettingManager
from src.arena.round import DebateRound
from src.models import Debater, DebaterConfig, JudgeFactory
import json

def test_pot_split_logic():
    print("Verifying Pot Split Logic...")
    ledger = TokenLedger(initial_balance=100.0)
    distributor = TokenDistributor(tokens_per_round=20.0)
    betting = BettingManager()
    
    # Setup stub agents
    deb_a = Debater(DebaterConfig(model_path="stub", name="Alpha"))
    deb_b = Debater(DebaterConfig(model_path="stub", name="Beta"))
    judge = JudgeFactory.create_simple("stub", name="Judge")
    
    # Manual round simulation via DebateRound but focusing on economy
    round_obj = DebateRound(deb_a, deb_b, judge, ledger, betting, distributor)
    
    # Mocking parts of a round to test distribution
    # Topic: Test
    # Alpha bets 10, Beta bets 0.
    # Final confidence: A=0.8, B=0.2.
    # Initial Pot: 20
    # Stakes: 10
    # Total Pot: 30
    # A gets: 30 * 0.8 = 24.
    # B gets: 30 * 0.2 = 6.
    
    print("\n--- Test Case: Alpha bets 10, Final Conf A=0.8 ---")
    ledger.register("Alpha")
    ledger.register("Beta")
    
    # Alpha bets
    bet_a = betting.place_bet("Alpha", 10, 1, ledger)
    print(f"Alpha Balance after bet: {ledger.balance('Alpha')} (Stake 10 + 5% Fee 0.5 deducted)")
    
    # Distribute Pot
    res = distributor.distribute_pot("Alpha", "Beta", 0.8, 0.2, 1, ledger, extra_pot_tokens=10.0)
    print(f"Pot Split: Alpha={res.tokens_a}, Beta={res.tokens_b}")
    print(f"Final Balances: Alpha={ledger.balance('Alpha')}, Beta={ledger.balance('Beta')}")
    
    expected_a = 100 - 10.5 + 24
    expected_b = 100 + 6
    
    print(f"Expected: Alpha={expected_a}, Beta={expected_b}")
    if abs(ledger.balance("Alpha") - expected_a) < 0.01:
        print("✅ Success!")
    else:
        print("❌ Failure!")

if __name__ == "__main__":
    test_pot_split_logic()
