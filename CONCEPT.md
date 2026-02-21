# Core Concept: Adversarial Token-Economy Debate

## The Big Idea

This project is an experimental environment for selecting better reasoning behavior under scarcity.

Two debaters argue across many rounds. Every meaningful action consumes tokens. Better judged arguments earn tokens. The system is meant to test whether economic pressure produces:
- better allocation of inference-time compute,
- more adaptive strategic behavior over time,
- and more compressed internal reasoning traces.

## Theoretical Framing

This project intentionally mirrors ideas from economics, evolution, and thermodynamics.

### Economics
- Tokens are a scarce budget.
- Decisions are investment choices under uncertainty.
- Fee structure creates negative EV for uninformed betting and rewards edge-aware behavior.
- Kelly-style sizing provides a normative baseline for proportional risk-taking.

### Evolution
- Tournament persistence creates selection pressure over policies, not just one-shot outputs.
- Agents that allocate compute better should survive longer and accumulate more balance.
- Pass/respond behavior, budget control, and adaptation after loss become selection signals.

### Thermodynamics (Analogy)
- Tokens are available energy for cognitive work.
- Generation/deliberation/search are work-like expenditures.
- Fees are friction (dissipation) that penalizes random action.
- Balance depletion and bankruptcy represent irreversible loss of usable budget.

The analogy is descriptive, not a physical claim, but it provides useful invariants:
- no free work,
- explicit energy accounting,
- and path-dependent survival dynamics.

## Design Philosophy

Emergent over prescribed.

The project prefers improving environment incentives and evaluation quality over hardcoded behavior rules. If behavior is degenerate, first ask whether the judge/economy signal is too noisy or gameable, instead of adding arbitrary penalties.

## Current Decision Model

Debater deliberation outputs a structured decision:
- `RESPOND`: place a bet, optionally use search (`use_search: true`), then generate a response.
- `PASS`: skip action this iteration.

Each deliberation also includes:
- `amount`: stake size,
- `max_budget`: maximum authorized economic tokens for the upcoming generation.

`max_budget` is converted into a hard generation token cap (`max_tokens`) in runtime.

## Round Flow (Current)

```text
Round N:
1. Generate initial arguments (cost deducted by LLM token usage).
2. Judge initial arguments and output confidences.
3. Optional initial bounty split (`split_pot_enabled`).
4. Iterative loop:
   - each debater chooses RESPOND or PASS (with wallet budget authorization),
   - deliberation cost is deducted,
   - RESPOND may call search and then generate under `max_budget`,
   - judge re-evaluates.
5. Terminate on mutual PASS, bankruptcy condition, or max iterations.
6. Distribute pot by final confidence, resolve bets, log transcript and ledger.
```

## Information Asymmetry

Debaters see:
- topic,
- arguments,
- confidence scores,
- own balance and balance delta.

Debaters do not see:
- judge internal reasoning prompt,
- opponent private `<thinking>`,
- opponent balance.

This is intended to reduce direct judge-pandering and preserve strategic uncertainty.

## Economy Mechanics (Current)

- LLM token usage maps to economic cost through `token_cost_ratio` (default 20:1).
- Deliberation, generation, summarization, and search all consume budget.
- Iteration fee scales as `min(0.05 * iteration, 0.50)`.
- Pot split is confidence-proportional (`tokens_per_round + locked_bets`).
- Optional split-pot initial bounty gives early non-zero payout.
- EV guard can conservatively override pathological bets in low-edge states.

## Architecture

Core runtime path:
- `src/arena/dynamic_round.py` for iterative round execution.
- `src/models/debater.py` for deliberation, wallet budget, and generation.
- `src/models/judge.py` for single/ensemble/consensus judging.
- `src/economy/*` for ledger, bets, and distribution.
- `src/logs/transcript.py` and `src/analysis/*` for evidence artifacts.

## System Contracts

Structured validation at LLM boundary:
- `JudgmentResponse`: validates confidences in `[0,1]`, normalizes to sum 1.0.
- `DeliberationResponse`: validates `decision in {RESPOND, PASS}`, `amount >= 0`, `max_budget >= 0`.

Validation failures do not silently become tie judgments.

## Implemented Capabilities

- Dynamic rounds with mutual-pass termination.
- Wallet phase (`max_budget`) threaded into generation hard cap.
- Deliberation token cost accounting.
- Optional search tool usage with explicit token cost.
- Self-summarization memory with explicit token cost.
- Multi-dimension judging and randomized argument order support.
- Strict runtime preflight and judge variance gating in tournament runs.
- Selection health dashboard and trajectory parsing tooling.

## Known Gaps and Risks

- Reasoning-quality trajectory metrics exist but need stronger longitudinal validation.
- Judge quality still determines whether economic signal is learnable or noisy.
- Some docs/configs can drift quickly as economics are tuned.
- Debt and elimination semantics need single-source clarity across prompt text and runtime checks.

## Roadmap

1. Ground-truth calibration topics for judge validity checks.
2. Stronger trajectory metrics for internal reasoning compression/synthesis over time.
3. Economic parameter derivation from explicit runway targets, not ad hoc constants.
4. Arena progression (tiering/ranking) only after evidence quality stabilizes.
