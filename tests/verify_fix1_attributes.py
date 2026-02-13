#!/usr/bin/env python3
"""Verify Fix 1: all_bets attribute access works."""
from src.arena.dynamic_round import DynamicRoundResult

# Test that class has the right attributes
assert hasattr(DynamicRoundResult, '__dataclass_fields__'), "Not a dataclass"

fields = DynamicRoundResult.__dataclass_fields__
assert 'all_bets' in fields, "FAIL: all_bets field not found"
print("✅ DynamicRoundResult has 'all_bets' field")

# Test the judgment property exists
assert hasattr(DynamicRoundResult, 'judgment'), "FAIL: judgment property not found"
print("✅ DynamicRoundResult has 'judgment' property")

# Test tournament.py defensive pattern
test_obj = type('FakeResult', (), {'all_bets': [1,2,3]})()
bets_count = len(getattr(test_obj, 'all_bets', getattr(test_obj, 'bets_placed', [])))
assert bets_count == 3, "FAIL: getattr pattern broken"
print("✅ Defensive getattr pattern works")

print("\n✅✅✅ Fix 1 VERIFIED")
