# Core Concept: Adversarial Token-Economy Debate

## Goals

This project serves two complementary research goals:

### 1. Train a Competitive Model at Lower Cost

Use adversarial debate under economic pressure to generate high-quality training data. The pipeline:

1. Small models debate under token scarcity, producing reasoning traces
2. Economic and evolutionary pressure selects for better strategies (survivors, winners, adapted behaviors)
3. Winning traces are exported as SFT examples and preference pairs
4. A student model is fine-tuned on this data to approximate frontier-quality reasoning at lower inference cost

The hypothesis is that scarcity-selected reasoning traces carry more signal per token than unconstrained generation — models forced to budget their thinking produce more focused, higher-quality arguments.

**Current state:** Steps 1-3 exist in code. Step 4 (actual training loop and evaluation of the trained model) is not yet implemented.

### 2. Observe Emergent Strategic Behavior

Rather than programming models to be strategic, this project creates an environment where strategic behavior may emerge from economic incentives. Key questions:

- Do models learn to allocate compute differently under budget pressure?
- Does adaptation after loss emerge without explicit instruction?
- Do models develop different strategies for different topic types?
- Does cross-round memory produce measurable behavioral shifts?

Early evidence: after implementing the "Wallet Phase" (forcing models to authorize budgets before generation), economy-related mentions in `<thinking>` tags increased from 1 to 8 per match. ADAPT_ON_LOSS directives show +0.020 adaptation gain — small but measurably positive.

## Design Philosophy

### Non-Arbitrariness

Every mechanism in the system should be grounded in a real-world principle, not invented as an ad hoc fix:

| Mechanism | Grounding | Why it's not arbitrary |
|-----------|-----------|----------------------|
| Token budgets | Economics: allocation under scarcity | Models face real resource constraints, not artificial turn limits |
| Betting with fees | Market microstructure: transaction costs | Fees create negative EV for uninformed aggression, rewarding edge-aware betting |
| Kelly criterion sizing | Information theory: optimal growth rate | Bet sizes scale with estimated edge, not fixed amounts |
| Multi-dimension judging | Evaluation theory: construct validity | Accuracy/responsiveness/development each measure distinct argument qualities |
| Scaling iteration fees | Mechanism design: termination incentives | Later iterations cost more, naturally encouraging convergence |
| Bankruptcy elimination | Evolution: selection pressure | Unfit strategies are removed, not penalized with arbitrary score deductions |
| Confidence-proportional payout | Pari-mutuel markets | Winner's share reflects judge confidence, not a fixed prize |

**Non-arbitrariness audit — current gaps:**

- `token_cost_ratio` (20:1 LLM tokens to economic tokens) is a tuning parameter without principled derivation. It works but should ideally be calibrated from empirical cost curves.
- Judge confidence clamping (5-95%) is a practical guard against extreme volatility. The range itself is somewhat arbitrary — a more principled approach would derive bounds from observed judge noise.
- `max_iterations` is a hard cap that prevents infinite loops but doesn't emerge from the economics. The scaling fees should theoretically handle termination pressure, but the hard cap remains as a safety net.
- The `split_pot_enabled` initial bounty is a design choice to prevent zero-payout early rounds. Its amount and existence are configurable but not derived from theory.

### Emergent Over Prescribed

When behavior is degenerate, the first question is: **is the evaluation signal or incentive structure broken?**

Example: when Beta won a tournament by doing nothing (all deliberations failed validation, defaulted to free PASS, conserved tokens while Alpha went bankrupt), the fix was not a PASS penalty. The fix was multi-dimension scoring where passivity naturally scores low on responsiveness and development dimensions. The judge became smarter, not the rules more restrictive.

## Theoretical Framing

### Economics
- Tokens are a scarce budget.
- Decisions are investment choices under uncertainty.
- Fee structure creates negative EV for uninformed betting and rewards edge-aware behavior.
- Kelly-style sizing provides a normative baseline for proportional risk-taking.

### Evolution
- Tournament persistence creates selection pressure over policies, not just one-shot outputs.
- Agents that allocate compute better should survive longer and accumulate more balance.
- Pass/respond behavior, budget control, and adaptation after loss become selection signals.
- Evolutionary campaigns mutate strategy profiles and select winners across generations.

### Thermodynamics (Analogy)
- Tokens are available energy for cognitive work.
- Generation/deliberation/search are work-like expenditures.
- Fees are friction (dissipation) that penalizes random action.
- Balance depletion and bankruptcy represent irreversible loss of usable budget.

The analogy is descriptive, not a physical claim, but it provides useful invariants: no free work, explicit energy accounting, and path-dependent survival dynamics.

## Current Decision Model

Debater deliberation outputs a structured decision:
- `RESPOND`: place a bet, optionally use search (`use_search: true`), then generate a response.
- `PASS`: skip action this iteration.

Each deliberation also includes:
- `amount`: stake size
- `max_budget`: maximum authorized economic tokens for the upcoming generation

`max_budget` is converted into a hard generation token cap (`max_tokens`) at runtime. This is the "Wallet Phase" — models must explicitly authorize spending before they can generate.

## Round Flow

```text
Round N:
1. Generate initial arguments (cost deducted by LLM token usage).
2. Judge initial arguments (multi-dimension: accuracy/responsiveness/development).
3. Optional initial bounty split (split_pot_enabled).
4. Iterative loop:
   - each debater deliberates with <thinking> and chooses RESPOND or PASS,
   - deliberation cost is deducted,
   - RESPOND: bet placed (stake + fee), optional search, generate under max_budget cap,
   - judge re-evaluates with comparative context (sees prior judgment),
   - observers track metrics.
5. Terminate on mutual PASS, bankruptcy, or max iterations.
6. Distribute pot by final confidence, resolve bets (sqrt convex reward curve), log transcript and ledger.
7. Audit round accounting (minted - burned == supply delta).
```

## Information Asymmetry

Debaters see:
- topic, arguments, confidence scores, own balance and balance delta

Debaters do not see:
- judge internal reasoning prompt, opponent private `<thinking>`, opponent balance

This preserves strategic uncertainty and reduces direct judge-pandering.

## Known Gaps and Risks

- **No training loop.** Training data is generated but no fine-tuning or evaluation pipeline exists yet.
- **No NPU runtime.** Intel NPU is a target but has zero implementation.
- **Judge quality determines everything.** If judge signal is noisy, economic optimization is optimizing noise. The 7b judge (stdev=0.024) is research-grade; the 1.5b judge (stdev=0.141) is not.
- **Token-cost ratio portability** across models/backends is weakly grounded.
- **Trajectory parsing** uses fragile emoji-based markdown splitting.
- **Pass rate too high** (0.83 observed vs ~0.35 target). Models still PASS too aggressively — an economy pressure tuning problem.

## Roadmap

1. Close the training loop — consume generated SFT/preference data, fine-tune a student model, evaluate against baseline.
2. Validate that economic pressure actually produces better training signal than unconstrained debate.
3. Reduce pass rate through economy pressure tuning (not arbitrary penalties).
4. Strengthen trajectory metrics for internal reasoning quality measurement.
5. Add NPU runtime path for cost-effective inference.
6. Scale to population tournaments (multi-model Swiss/challenger scheduling).
