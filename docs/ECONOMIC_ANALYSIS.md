# Economic Parameter Analysis

## Scope

This document explains what is currently tunable, what is mathematically grounded, and how to calibrate economy parameters without guesswork.

## Current Configuration Reality

There is not one single economy setting in this repo. Multiple configs are used for different run modes.

| Source | Initial Balance | Max Debt | Tokens per Round | Notes |
|---|---:|---:|---:|---|
| `src/config_loader.py` defaults | 200 | 50 | 100 | Loader fallback defaults |
| `configs/tournament_config.yaml` | 350 | 50 | 120 | General local config |
| `configs/ollama_tournament_recommended.yaml` | 420 | 105 | 85 | Recommended Ollama scale path |
| `configs/vllm_tournament_recommended.yaml` | 420 | 105 | 85 | Recommended strict vLLM research path |

Interpretation: treat values as profile-specific, not universal constants.

## Mechanics That Matter

- Cost accounting includes deliberation, generation, summarization, and optional search.
- Fee schedule scales by iteration in dynamic rounds: `min(0.05 * iteration, 0.50)`.
- Pot split is confidence-proportional over `tokens_per_round + locked_bets`.
- EV guard can reduce pathological over-betting for low edge conditions.

## Formulas

### 1. Expected Value Per Bet

```text
EV = (p_win * payout) - ((1 - p_win) * stake) - fee
```

For equal-skill agents (`p_win ~ 0.5`), fee makes random betting negative EV by design.
That is desirable: random aggression should lose to selective aggression.

### 2. Kelly Fraction (Sizing Baseline)

```text
f* = (p(b + 1) - 1) / b
```

- `p`: estimated win probability
- `b`: net odds per unit stake (after fees/effective payout assumptions)

Use this as a sanity baseline for whether bet sizes scale with bankroll and edge.

### 3. Survival Runway

```text
runway_rounds ~= initial_usable_budget / expected_net_loss_per_round
```

Where expected per-round loss should include:
- deliberation cost,
- generation cost,
- expected lost stake,
- expected fee burn,
- minus expected pot returns.

## Calibration Workflow (Recommended)

1. Pick one invariant with the team
   - Example: a consistently losing model should survive at least `N` rounds to allow adaptation.

2. Estimate per-round cost components from recent logs
   - Use transcript/ledger artifacts, not assumptions.

3. Solve for initial budget and pot scale
   - Increase runway via initial balance or reduced burn.
   - Maintain negative EV for uninformed betting via fee structure.

4. Validate by simulation and stress tests
   - Run repeated tournaments and compare observed runway vs target.
   - Gate on judge variance before interpreting economy dynamics.

5. Lock profile values per run mode
   - Keep separate calibrated profiles for local Ollama and strict vLLM if needed.

## Known Risks

- Judge noise can dominate economy signal if variance is too high.
- Mixed elimination semantics across runtime layers can confuse runway interpretation.
- Token-cost ratio portability across models/backends remains a weakly grounded assumption.

## Practical Guidance

- Do not optimize for one lucky run.
- Report means/variance across repeated runs.
- Keep economics changes coupled to explicit hypotheses and metrics in artifacts.
