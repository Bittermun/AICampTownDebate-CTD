#!/usr/bin/env python3
"""Run all critical bug fix verification scripts."""
import subprocess
import sys

scripts = [
    "verify_fix1_attributes.py",
    "verify_fix2_parsing.py", 
    "verify_fix3_randomize.py",
    "verify_fix4_fees.py",
    "verify_fix5_clamping.py",
    "verify_fix6_validation_cost.py",
]

print("="*60)
print("RUNNING ALL VERIFICATION SCRIPTS")
print("="*60)

passed = 0
failed = 0

for script in scripts:
    print(f"\n--- {script} ---")
    result = subprocess.run([sys.executable, script], capture_output=False)
    if result.returncode == 0:
        passed += 1
    else:
        failed += 1
        print(f"❌ {script} FAILED")

print("\n" + "="*60)
print(f"RESULTS: {passed} passed, {failed} failed")
print("="*60)

sys.exit(0 if failed == 0 else 1)
