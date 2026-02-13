#!/usr/bin/env python3
"""Verify Fix 4: Fee economics observed (simplified)."""
from src.economy.betting import BettingManager
from src.economy.ledger import TokenLedger

ledger = TokenLedger(initial_balance=100, max_debt=50)
ledger.register("A")
betting = BettingManager(fee_rate=0.10)

print("Testing fee calculation:")
print(f"  Starting balance: {ledger.balance('A')}")

# Place one bet
bet = betting.place_bet("A", 20.0, round_id=1, ledger=ledger)
if bet:
    print(f"  Bet placed: amount={bet.amount}, fee={bet.fee_paid}")
    print(f"  Remaining balance: {ledger.balance('A')}")
    assert bet.fee_paid == 2.0, f"Expected fee 2.0, got {bet.fee_paid}"
    print("✅ Fee calculated correctly (10% of 20 = 2)")
else:
    print("❌ Bet failed to place")
    exit(1)

# Check total deduction
expected = 100 - 20 - 2  # principal + fee
actual = ledger.balance("A")
assert abs(actual - expected) < 0.01, f"Expected {expected}, got {actual}"
print(f"✅ Balance deducted correctly: 100 - 22 = {actual}")

print("\n✅✅✅ Fix 4 VERIFIED")
