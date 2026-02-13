
from src.economy import TokenLedger, TokenDistributor
from src.models import Judgment

def test_distribution_integrity():
    print("Testing Token Distribution Integrity...")
    ledger = TokenLedger(initial_balance=100.0)
    distributor = TokenDistributor(tokens_per_round=20.0)
    
    ledger.register("Alpha")
    ledger.register("Beta")
    
    # Simulate Round 1
    print("\n--- Round 1: 0.4 A vs 0.6 B ---")
    res1 = distributor.distribute_linear("Alpha", "Beta", 0.4, 0.6, 1, ledger)
    print(f"Awarded: A={res1.tokens_a}, B={res1.tokens_b}")
    print(f"Balances: A={ledger.balance('Alpha')}, B={ledger.balance('Beta')}")
    
    # Check for swap
    if res1.tokens_a == 12 or ledger.balance("Alpha") == 112:
        print("❌ BUG FOUND: Round 1 tokens are swapped!")
    
    # Simulate Round 2
    print("\n--- Round 2: 0.2 A vs 0.8 B ---")
    res2 = distributor.distribute_linear("Alpha", "Beta", 0.2, 0.8, 2, ledger)
    print(f"Awarded: A={res2.tokens_a}, B={res2.tokens_b}")
    print(f"Balances: A={ledger.balance('Alpha')}, B={ledger.balance('Beta')}")

    if res2.tokens_a == 14:
        print("❌ BUG FOUND: Round 2 tokens are lagging from Round 3 (swapped)!")

if __name__ == "__main__":
    test_distribution_integrity()
