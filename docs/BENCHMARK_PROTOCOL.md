# Benchmark Protocol (Phase 1)

## Purpose

This protocol separates two different goals:

1. Truth/reasoning validation (benchmark gates): "Is the model actually good?"
2. Operational ranking (league): "Who is currently winning in this arena?"

League rank must never be treated as proof of truth quality without benchmark pass.

The machine-readable policy is in `configs/benchmark_phase1.yaml`.

## Core Principles

1. Strict runtime only for research claims.
2. Judge reliability must pass variance and calibration gates first.
3. Accounting invariants must hold (no untracked drift).
4. Results must be reproducible across seeds.
5. ELO/tier is an operations layer, not the scientific layer.

## Phase 1 Bundle

1. Truth core:
   - MMLU-Pro (120)
   - GPQA (60)
   - TruthfulQA (80)
2. Reasoning core:
   - GSM8K (100)
   - HotpotQA (60)
   - FEVER (80)
3. Adversarial robustness:
   - Internal symmetry pairs (40 pairs)
   - Internal premise traps (30)
4. Economy/adaptation:
   - Internal budget-sensitive tasks (30)
   - Internal longitudinal adaptation tasks (20)

## Run Procedure

1. Preflight all models/backends.
2. Run judge variance gate.
3. Run judge calibration gate.
4. Run benchmark groups over seeds `[101, 202, 303]`.
5. Compute group scores, aggregate score, and stability stats.
6. Record selection-health and accounting audit outputs.
7. Update league ratings only for valid runs.

## Pass/Fail Conditions

1. Judge variance pass:
   - `stdev <= 0.05`
   - `mean_a >= 0.55`
2. Judge calibration pass:
   - fixed-case pass rate `>= 0.75`
3. Accounting pass:
   - supply drift `<= 0.01` per round
4. Aggregate benchmark pass:
   - weighted score `>= 0.60`
   - max seed stdev `<= 0.06`

If any required gate fails, the run is invalid for scientific claims.

## ELO/Tier Policy

1. Start at ELO 1500.
2. K-factor:
   - provisional first 30 matches: `K=32`
   - stable: `K=16`
3. Matchmaking:
   - preferred window `+/-100 ELO`
4. Tier bands:
   - Bronze: `<1400`
   - Silver: `1400-1599`
   - Gold: `1600-1799`
   - Platinum: `>=1800`

## Champion Freeze Policy

Use freeze to create a stable reference champion.

Freeze requirements:

1. Hold top performance across 3 windows.
2. Each window passes all gates.
3. Each window passes benchmark aggregate threshold.

Frozen manifest must include:

1. Model identifier/version/hash.
2. Prompt hash and config hash.
3. Judge config hash.
4. Tooling/version and seed set.
5. Artifact paths.

## Challenger Policy

A challenger replaces a frozen champion only if it:

1. Wins head-to-head (minimum 30 matches),
2. Beats champion on aggregate benchmark score,
3. Beats champion on economy/adaptation score,
4. Shows a positive effect size (`>= 0.02`) with confidence intervals.

## Practical Notes

1. Start with small sample sizes for smoke checks, then scale to full bundle.
2. Keep internal benchmark items versioned and immutable once published.
3. Do not change gates mid-comparison window.
