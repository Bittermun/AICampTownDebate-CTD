# Evaluation Contract

This project uses a strict order of operations for any quality claim:

1. Mechanics must be valid.
2. Measurement must be trustworthy.
3. Only then are performance claims allowed.

If any earlier stage fails, stop and fix it before claiming model gains.

## Claim Levels

- `L0 Plumbing`
  - Runtime works, artifacts exist.
  - No quality claim allowed.
- `L1 Valid Run`
  - Strict run passes validity checks.
  - You can claim "valid execution" only.
- `L2 Quality Claim`
  - Valid run plus trustworthy, model-dependent scoring.
  - You can claim quality movement.

## Non-Negotiable Invariants

1. Settlement invariants
   - Every accepted bet must resolve (no pending bets after round finalize).
   - Bet settlement must not depend on transcript logging being enabled.
   - Transcript bet payout lines must match ledger `bet_won:*` totals per round/speaker.
2. Accounting invariants
   - Supply drift must stay within configured tolerance.
   - Mint/burn math must reconcile at round and run level.
3. Action invariants
   - `RESPOND` must imply a valid accepted stake.
   - Invalid/blocked stake attempts must be normalized to `HOLD/PASS`.
4. Semantics invariants
   - Action labels used in prompts/logs must be interpreted consistently in analysis (`HOLD` equivalent to pass where intended).

## Measurement Provenance Rules

Every reported metric must be tagged:

- `model_derived`: depends on current model outputs.
- `fixture_static`: fixed by fixture `metric_values`.
- `hybrid`: mixed source.

Quality claims require the key metrics to be `model_derived` or explicitly justified `hybrid`.
If key metrics are `fixture_static`, the run is capped at `L1`.

## Minimum Evidence Block For Any Report

Every report must include:

1. Runtime + command provenance
   - backend, model IDs, config path, exact command lines.
2. Artifact provenance
   - summary path, transcript path, ledger path, timestamp.
3. Gate outcomes
   - judge variance/calibration, validity pass, trajectory checks.
4. Provenance table for top-level scores
   - source type (`model_derived`/`fixture_static`/`hybrid`).
5. Incident log
   - failure, root cause, fix, prevention.

## Blockers That Must Hard-Fail Claims

Any one of these blocks `L2` claims:

- unresolved settlement mismatch,
- metric provenance unknown,
- static-score ceiling not acknowledged,
- contradictory elimination/scoring semantics between prompt and runtime,
- missing reproducibility artifacts.

## Required Tools

Before claiming quality movement, run:

1. `python scripts/audit_score_ceiling.py --config configs/benchmark_phase1.yaml --fixtures-dir benchmarks/fixtures`
2. `python scripts/reconcile_settlement.py --transcript <..._transcript.json> --ledger <..._ledger.json>`
3. `python tests/test_econ_invariants.py`

