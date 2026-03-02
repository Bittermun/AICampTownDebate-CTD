# Next AI Bootstrap

This file is a fast operational handoff for the next AI/Codex run.

## First 10 Minutes Checklist

1. Read:
   - `docs/EVALUATION_CONTRACT.md`
   - `docs/TONIGHT_Q1B_REPORT_20260301.md`
2. Verify runtime endpoints:
   - OpenAI-compatible endpoint health (`/v1/models`).
3. Run fast integrity checks:
   - `python tests/test_response_models.py`
   - `python tests/test_benchmark_runner.py`
   - `python tests/test_econ_invariants.py`
4. Run score-ceiling audit:
   - `python scripts/audit_score_ceiling.py --config configs/benchmark_phase1.yaml --fixtures-dir benchmarks/fixtures`

## What Not To Misinterpret

1. Fixture-mode aggregate can be effectively fixed by static fixture metrics.
2. A valid strict run does not automatically mean a quality improvement claim is justified.
3. Judge upgrades can fix gates while leaving aggregate unchanged.

## Required Pre-Claim Commands

1. Score ceiling:
   - `python scripts/audit_score_ceiling.py --config configs/benchmark_phase1.yaml --fixtures-dir benchmarks/fixtures --output logs/score_ceiling_audit.json`
2. Settlement reconciliation:
   - `python scripts/reconcile_settlement.py --transcript <transcript.json> --ledger <ledger.json> --output <reconcile.json>`
3. Strict run:
   - `python tests/run_phase1_benchmark.py ...`

## Decision Policy

1. If ceiling audit says pass is unreachable in current fixture mode:
   - Do not iterate model prompts hoping for pass.
   - Choose explicitly: policy threshold change, live-data path, or fixture recalibration with audit trail.
2. If settlement reconciliation fails:
   - Fix mechanics first; freeze all quality claims.

## Safe Defaults

1. Keep runs short while debugging (`--seeds 101`, fewer rounds/iterations).
2. Preserve strict mode for claim-bearing runs.
3. Prefer reproducible artifacts over ad hoc console interpretation.

