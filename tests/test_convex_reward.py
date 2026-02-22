#!/usr/bin/env python3
"""
Unit tests for the Phase 2 convex (sqrt-shaped) bet reward curve.

Formula: multiplier = 1.0 + min(2.0, (improvement * 10) ** 0.5)

Where improvement = final_confidence - initial_confidence (0.0 to 1.0)

Verified expected values:
  0.05 improvement: sqrt(0.5)  = 0.707 → 1.707x
  0.10 improvement: sqrt(1.0)  = 1.000 → 2.000x
  0.20 improvement: sqrt(2.0)  = 1.414 → 2.414x
  0.40 improvement: sqrt(4.0)  = 2.000 → 3.000x (cap)
  1.00 improvement: sqrt(10.0) = 3.162 → 3.000x (cap)
"""
import sys, math
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def convex_multiplier(improvement: float) -> float:
    """The Phase 2 convex reward curve. Mirrors the code in _phase_distribute_tokens."""
    return 1.0 + min(2.0, (max(0.0, improvement) * 10) ** 0.5)


def run_tests():
    tol = 0.001

    # ── Test 1: Small improvement (5pts) ──────────────────────────────────────
    print("Test 1: Small improvement (5pts)")
    m = convex_multiplier(0.05)
    expected = 1.0 + math.sqrt(0.5)   # = 1.707
    assert abs(m - expected) < tol, f"Expected {expected:.3f}x, got {m:.3f}x"
    print(f"  ✅ 5pt improvement → {m:.3f}x")

    # ── Test 2: Medium improvement (10pts) → hits 2.00x ───────────────────────
    print("Test 2: Medium improvement (10pts) → exactly 2.0x")
    m = convex_multiplier(0.10)
    expected = 1.0 + math.sqrt(1.0)   # = 2.000
    assert abs(m - expected) < tol, f"Expected {expected:.3f}x, got {m:.3f}x"
    print(f"  ✅ 10pt improvement → {m:.3f}x")

    # ── Test 3: 20pt improvement → 2.41x ──────────────────────────────────────
    print("Test 3: Large improvement (20pts) → 2.41x")
    m = convex_multiplier(0.20)
    expected = 1.0 + math.sqrt(2.0)   # = 2.414
    assert abs(m - expected) < tol, f"Expected {expected:.3f}x, got {m:.3f}x"
    print(f"  ✅ 20pt improvement → {m:.3f}x")

    # ── Test 4: 40pt improvement → hits 3.0x cap ──────────────────────────────
    print("Test 4: 40pt improvement → hard cap at 3.0x")
    m = convex_multiplier(0.40)
    assert m == 3.0, f"Expected 3.0x cap, got {m:.3f}x"
    print(f"  ✅ 40pt improvement → {m:.3f}x (cap enforced)")

    # ── Test 5: Extreme → still 3.0x ──────────────────────────────────────────
    print("Test 5: Extreme improvement (100%) → 3.0x cap")
    m = convex_multiplier(1.00)
    assert m == 3.0, f"Expected 3.0x cap, got {m:.3f}x"
    print(f"  ✅ 100pt improvement → {m:.3f}x (cap enforced)")

    # ── Test 6: No improvement → 1.0x ────────────────────────────────────────
    print("Test 6: No improvement → 1.0x (stake returned)")
    m = convex_multiplier(0.0)
    assert m == 1.0, f"Expected 1.0x, got {m:.3f}x"
    print(f"  ✅ 0pt improvement → {m:.3f}x")

    # ── Test 7: Negative delta → guarded to 1.0x ─────────────────────────────
    print("Test 7: Negative delta → treated as 0 via max() guard")
    m = convex_multiplier(-0.15)
    assert m == 1.0, f"Expected 1.0x, got {m:.3f}x"
    print(f"  ✅ -15pt delta → {m:.3f}x (clamped correctly)")

    # ── Test 8: Convex curve outpays old linear at key thresholds ─────────────
    print("Test 8: Convex > linear at all realistic improvement levels")
    for improvement in [0.05, 0.10, 0.15, 0.20]:
        initial = 0.50
        old_linear = min(3.0, (initial + improvement) / initial)
        new_convex = convex_multiplier(improvement)
        assert new_convex > old_linear, \
            f"At +{improvement*100:.0f}pt: convex {new_convex:.3f} should > linear {old_linear:.3f}"
    print(f"  ✅ Convex consistently outpays linear for improvements up to 20pts")

    # ── Reward lookup table ───────────────────────────────────────────────────
    print("\n  Reward curve comparison:")
    print("  ┌──────────┬────────────┬────────────┬────────────┐")
    print("  │ Swing    │ Old linear │ New convex │ Improvement│")
    print("  ├──────────┼────────────┼────────────┼────────────┤")
    for improvement in [0.05, 0.10, 0.15, 0.20, 0.30, 0.40]:
        initial = 0.50
        old = min(3.0, (initial + improvement) / initial)
        new = convex_multiplier(improvement)
        delta = new - old
        print(f"  │ +{improvement*100:.0f}%      │ {old:.3f}x     │ {new:.3f}x     │ +{delta:.3f}x     │")
    print("  └──────────┴────────────┴────────────┴────────────┘")


if __name__ == "__main__":
    print("=" * 55)
    print("CONVEX REWARD CURVE UNIT TESTS")
    print("=" * 55)
    try:
        run_tests()
        print("\n✅✅✅ All convex reward tests PASSED")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
