#!/usr/bin/env python3
"""
Comprehensive test suite for all tournament system components.

Best Practice: Each feature gets its own isolated test that can run independently.
Run all: python tests/test_suite.py
Run one: python tests/test_suite.py test_judge_clamping
"""
import subprocess
import sys
import os

# Force UTF-8 encoding on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Change to project root
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TESTS = [
    # Legacy compatibility checks
    ("Attribute Compatibility", "tests/verify_fix1_attributes.py"),
    ("JSON Parsing Edge Cases", "tests/verify_fix2_parsing.py"),
    ("Position Randomization", "tests/verify_fix3_randomize.py"),
    ("Fee Economics", "tests/verify_fix4_fees.py"),
    ("Judge Clamping", "tests/verify_fix5_clamping.py"),
    ("Validation Token Cost", "tests/verify_fix6_validation_cost.py"),
    ("Multi-Dim Model", "tests/verify_multidim_judge.py"),
    ("Judge Integration", "tests/verify_judge_integration.py"),

    # Core model and prompting contracts
    ("Response Models", "tests/test_response_models.py"),
    ("Prompt Rule Cards", "tests/test_prompt_rule_cards.py"),

    # Benchmark and provenance contracts (local, no live runtime required)
    ("Benchmark Config Parse", "tests/test_benchmark_config_parse.py"),
    ("Benchmark Datasets", "tests/test_benchmark_datasets.py"),
    ("Benchmark Scoring", "tests/test_benchmark_scoring.py"),
    ("Benchmark Score Sources", "tests/test_benchmark_score_sources.py"),
    ("Benchmark Source Modes", "tests/test_benchmark_source_mode_overrides.py"),
    ("Benchmark Runner HOLD Semantics", "tests/test_benchmark_runner.py"),
    ("Benchmark Batch Utils", "tests/test_benchmark_batch_utils.py"),
    ("Benchmark Registry", "tests/test_benchmark_registry.py"),
    ("Evolution Campaign", "tests/test_evolution_campaign.py"),

    # Economy and analysis invariants
    ("Economy Invariants", "tests/test_econ_invariants.py"),
    ("Selection Health HOLD Semantics", "tests/test_selection_health_hold_semantics.py"),
]

def run_test(name: str, script: str) -> bool:
    """Run a single test script, return True if passed."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    
    try:
        # Run with UTF-8 encoding
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONPATH'] = os.getcwd() # Project root
        
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
            encoding='utf-8',
            errors='replace'
        )
        
        if result.returncode == 0:
            # Show only last few lines (summary)
            lines = result.stdout.strip().split('\n')
            for line in lines[-3:]:
                print(line)
            print(f"[PASS] {name}")
            return True
        else:
            print(result.stdout)
            print(result.stderr)
            print(f"[FAIL] {name}")
            return False
            
    except FileNotFoundError:
        print(f"[SKIP] {name}: Script not found ({script})")
        return False
    except subprocess.TimeoutExpired:
        print(f"[FAIL] {name}: TIMEOUT")
        return False

def run_all_tests():
    """Run all tests and report summary."""
    print("\n" + "="*60)
    print("TOKEN-DEBATE TEST SUITE")
    print("="*60)
    
    passed = 0
    failed = 0
    skipped = 0
    
    for name, script in TESTS:
        if os.path.exists(script):
            if run_test(name, script):
                passed += 1
            else:
                failed += 1
        else:
            print(f"[SKIP] {name}: Not found")
            skipped += 1
    
    print("\n" + "="*60)
    print(f"SUMMARY: {passed} passed, {failed} failed, {skipped} skipped")
    print("="*60)
    
    return failed == 0

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        for name, script in TESTS:
            if test_name.lower() in name.lower() or test_name == script:
                run_test(name, script)
                break
        else:
            print(f"Test '{test_name}' not found")
            print("Available tests:")
            for name, script in TESTS:
                print(f"  - {name}: {script}")
    else:
        # Run all
        success = run_all_tests()
        sys.exit(0 if success else 1)
