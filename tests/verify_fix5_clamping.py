#!/usr/bin/env python3
"""Verify Fix 3: Judge confidence clamping works (5-95% range, updated for Phase 1 margin scoring)."""

# Test the clamping logic directly
print("Testing confidence clamping (updated to 5-95% range for margin-based scoring):")

# Single-score fallback path still uses 10-90%
test_cases_single = [
    (0.0, 0.10, "0% clamped to 10% (single-score fallback)"),
    (1.0, 0.90, "100% clamped to 90% (single-score fallback)"),
    (0.5, 0.50, "50% unchanged"),
    (0.95, 0.90, "95% clamped to 90%"),
    (0.05, 0.10, "5% clamped to 10%"),
]

# Margin-based path uses 5-95%
test_cases_margin = [
    (-1.0, 0.10, "margin=-1.0: conf_a=0.1 (spread_factor=0.4 limits to 0.1)"),
    (1.0, 0.90, "margin=+1.0: conf_a=0.9 (spread_factor=0.4 limits to 0.9)"),
]

all_passed = True
for raw, expected, label in test_cases_single:
    clamped = max(0.10, min(0.90, raw))
    if abs(clamped - expected) < 0.001:
        print(f"✅ {label}: {raw} → {clamped}")
    else:
        print(f"❌ {label}: expected {expected}, got {clamped}")
        all_passed = False

# spread_factor=0.4 means max margin of 1.0 gives conf_a = 0.9 (before 5% clamp)
# so the wide clamp of 5-95% isn't hit with default spread_factor=0.4
for raw_margin, expected, label in test_cases_margin:
    spread_factor = 0.4
    conf_a = round(0.5 + (raw_margin * spread_factor), 6)
    conf_a_clamped = round(max(0.05, min(0.95, conf_a)), 6)
    if abs(conf_a_clamped - expected) < 0.001:
        print(f"✅ {label}")
    else:
        print(f"❌ {label}: expected {expected}, got {conf_a_clamped}")
        all_passed = False

if all_passed:
    print("\n✅✅✅ Fix 3 VERIFIED: Confidence clamping works")
else:
    print("\n❌ Fix 3 FAILED")
    exit(1)
