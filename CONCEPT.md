# Core Concept: Adversarial Token-Economy Debate

## The Big Idea

Train AI models to develop efficient internal reasoning through **inference-time compute** and **mesa-cognition** by placing them in an adversarial debate tournament with a persistent token economy.

Unlike standard debate training (OpenAI 2018), this system adds:
- **Economic stakes** that persist across rounds
- **Betting mechanics** where models wager on their arguments
- **Actual token cost** for generating responses (not abstract chips)
- **Debt systems** allowing strategic resource allocation
- **Tiered arenas** for skill-matched competition

## Design Philosophy

**Emergent over Prescribed.** This system aims for *dialectic* reasoning (collaborative truth-seeking) rather than *eristic* debate (winning at any cost). We avoid prescribing what models should think about; instead, economic pressure creates selection for efficient meta-cognition. Prompts are minimal and autonomy-allowing — the model decides what's worth remembering, what strategy to use, and how to reason internally.


## Key Terminology

| Term | Definition |
|------|------------|
| **Debater** | Model that generates arguments on a topic |
| **Judge** | Modular system (single LLM, Ensemble, or Consensus/Instructor) |
| **Token (economic)** | Currency earned from good arguments, spent on responses |
| **Token (LLM)** | Actual compute cost of generating words (~2-3 per word) |
| **Bet** | Tokens staked on counter-arguments or research |
| **Research** | Spending tokens to strengthen your OWN position (not refutation) |
| **Refutation** | Counter-argument attacking opponent's position |
| **Debt** | Negative token balance; creates efficiency pressure |
| **Arena Tier** | Skill level; models move up/down based on performance |
| **Fee** | Token cost for betting; prevents degenerate strategies |
| **Truth-Focus Question** | Verification question to catch mutual lying |

## Round Flow (Revised)

```
Round N:
1. Debaters receive topic (they DO NOT see each other's prior arguments)
2. Each generates initial argument (costs LLM tokens from balance)
3. Judge evaluates → awards economic tokens based on confidence
4. Debaters see CONFIDENCE SCORES but NOT judge's reasoning (prevents pandering)
5. Each debater chooses:
   - BET on REFUTATION (counter opponent's argument)
   - BET on RESEARCH (strengthen own argument without seeing opponent)
   - PASS (save tokens)
6. If betting: spend tokens on additional generation
7. Judge re-evaluates → bets resolved based on confidence change
8. **Payouts Logged**: WON/LOST status and final tokens added to transcript
9. Balances persist to Round N+1
```

## Token Economy Rules (To Be Refined)

**Core economics:**
- Initial balance: 200 tokens
- Cost per response: ~proportional to LLM tokens used (20:1 ratio)
- **Deliberation cost**: Debaters pay for betting decisions (thinking isn't free)
- Award per round: Pot split based on final confidence
- **Scaling Fee (Dynamic Rounds)**: 5% per iteration (Burned), capped at 50%
- Bet multiplier on win: Stake returned via Pot Split weight

**Split Pot (Initial Bounty):**
- Optional `split_pot_enabled` distributes a fixed bounty (default 40 tokens) after initial arguments
- Guarantees both debaters earn something before betting begins
- Reduces "all-or-nothing" gambling behavior

**Key constraint:** Award rate should exceed average generation cost, so models accumulate tokens over time if they argue efficiently. Verbosity is punished.

## Information Asymmetry

| What Debaters See | What Debaters DON'T See |
|-------------------|-------------------------|
| Topic | Judge's reasoning |
| Opponent's arguments (after initial) | Judge's identity/prompt |
| Confidence scores & Standing (Lead/Trail) | Other debater's token balance |
| Own balance and debt | Future topics |

**Rationale:** Hiding judge reasoning prevents debaters from learning to pander to specific phrasings. They must learn what *actually* constitutes a good argument.


## Research vs. Refutation

Debaters can choose TWO types of betting:

| Type | What it does | When to use |
|------|--------------|-------------|
| **Refutation** | Generate counter-argument to opponent | When opponent's argument has clear weaknesses |
| **Research** | Generate additional support for YOUR argument | When you're confident in your position but want to strengthen it |

This allows models to develop different strategies beyond pure adversarial attack.

## Modular Multi-Agent Judging

Evaluation is no longer limited to a single model. The system supports:
- **LLMJudge**: Standard single-model evaluation.
- **EnsembleJudge**: Aggregates scores from multiple models (majority/mean).
- **Consensus/Instructor Judge**: A council of sub-judges provides notes to a "Senior Instructor" model which synthesizes the final reasoning and score.

## Configuration System

Tournament parameters are defined via YAML configuration files:

```yaml
models:
  debaters:
    - name: "Alpha"
      model: "qwen2.5:7b"
    - name: "Beta"
      model: "llama3:8b"
  judges:
    - model: "qwen2.5:1.5b"
      weight: 1.0

economy:
  initial_balance: 200
  split_pot_enabled: true
  initial_pot_amount: 40

rounds:
  max_iterations: 10
  topic: "Should AI be regulated?"
```

**Usage:** `python demo_dynamic.py --config configs/tournament_config.yaml`

This allows:
- Different models for each debater (asymmetric capability testing)
- Ensemble judges with weighted averaging
- Per-experiment economy tuning


## LLM-Driven Deliberation

**The betting decision is NOT a heuristic—it is LLM-driven.** Before choosing REFUTE, RESEARCH, or PASS, the debater model explicitly reasons about its strategy. This is where **inference-time compute** and **mesa-cognition** emerge.

### Deliberation Prompt Structure
```
=== YOUR SITUATION ===
Your balance: {balance} tokens
Your argument: [summary]
Opponent's argument: [summary]

=== STRATEGIC OPTIONS ===
1. REFUTE - Counter opponent's argument
2. RESEARCH - Strengthen your own argument
3. PASS - Save tokens for future rounds

REASONING: [One sentence explaining your choice]
DECISION: [REFUTE or RESEARCH or PASS]
AMOUNT: [0-N]
```

### Why This Matters
- The debater must **explicitly justify** its strategy
- Reasoning is captured in the transcript for analysis
- Creates selection pressure for *strategic planning*, not just generation
- Enables future fine-tuning on high-quality deliberation traces

## Why This Might Work

1. **Token scarcity → efficient reasoning** (can't brute-force)
2. **Actual token cost → compressed language** (verbosity is expensive)
3. **Debt pressure → no lazy strategies**
4. **Betting → skin in the game**
5. **Amnesiac judges → harder to exploit consistently**
6. **Hidden judge reasoning → no pandering optimization**
7. **Long-term persistence → develops planning/strategy**
8. **LLM-driven deliberation → explicit strategic reasoning**

## Known Concerns

| Concern | Mitigation |
|---------|------------|
| Desperation gambling (debt spiral) | Bankruptcy/reset mechanics (TBD) |
| Collusion between debaters | Truth-focus questions, adversarial auditors |
| Reward hacking | Multi-judge, betting fees as friction |
| Opacity of internal reasoning | Future: interpretability hooks |
| Running out of tokens too fast | Award rate > average cost; tune ratio |

## Related Work

| Prior Work | Key Distinction |
|------------|-----------------|
| **AI Safety via Debate** (Irving et al.) | No economy, no persistent state |
| **Constitutional AI** (Anthropic) | Self-critique without external adversary |
| **Futarchy** (Hanson) | Prediction markets for governance, not reasoning |
| **Multi-Agent Debate** (Du et al.) | No token economy, no betting mechanics |
| **Chain-of-Thought** (Wei et al.) | No economic pressure on reasoning length |

## Goal: Inference-Time Compute & Mesa-Cognition

**Inference-time compute**: Additional reasoning steps at generation time (chain-of-thought, self-reflection).

**Mesa-cognition**: Internal optimization processes that emerge within the model during training.

We want models to develop:
- Compressed, reusable reasoning patterns
- Long-term strategic planning
- Efficient internal representations
- Research vs. refutation strategy selection

## Key Innovations (Implemented)

### 1. Chain-of-Thought with `<thinking>` Tags

Debaters can use `<thinking></thinking>` tags for private reasoning before responding:
- **Extracted before JSON parsing** in deliberation
- **Hidden from opponent and judge** but logged for mesa-cognition analysis
- **Still costs tokens** — thinking isn't free

This creates implicit selection pressure for *efficient* internal reasoning.

### 2. Web Search via ResearchTool

Debaters can execute real web searches during the RESEARCH phase:
```python
tool = get_research_tool()
result = tool.search("AI regulation history")
# Dynamic cost: ~5-20 tokens based on content retrieved
```
- Uses **DuckDuckGo** for search
- **Dynamic token cost** based on query length + content retrieved
- Search results synthesized into argument via LLM

### 3. Self-Summarization Memory

To prevent context bloat, debaters self-summarize after each content generation:
- Triggered when argument history > 400 chars
- Compresses to ~80 words preserving thesis + key evidence
- **Costs tokens** — memory management is an economic decision
- Prevents "drift" in long debates while maintaining strategic continuity

### 4. Async Parallel Generation

Initial arguments generated concurrently via `asyncio.gather`:
- Reduces wall-clock time by ~50%
- vLLM backend stub prepared for future production scale

## Architecture: Phase-Based Round Execution

Each debate round now executes as a **pipeline of discrete phases**, each with explicit inputs and outputs:

```
RoundContext (state container)
    │
    ├─ Phase 1: Generate Arguments
    │     └─ Debaters generate initial arguments, costs deducted
    │
    ├─ Phase 2: Initial Judgment  
    │     └─ Amnesiac judge evaluates, confidence scores recorded
    │
    ├─ Phase 3: Betting
    │     └─ LLM-driven deliberation → REFUTE / RESEARCH / PASS
    │
    ├─ Phase 4: Final Judgment
    │     └─ Re-evaluate with counter-arguments/research included
    │
    └─ Phase 5: Token Distribution
          └─ Pot split via confidence ratio, bet outcomes logged
```

This design allows new phases (e.g., Truth-Focus questions) to be inserted without modifying existing logic.

## System Contracts (Implemented)

The system now enforces strict contracts at the LLM boundary:

| Contract | Purpose |
|----------|---------|
| `JudgmentResponse` | Validates confidence_a, confidence_b ∈ [0,1], auto-normalizes to sum=1.0 |
| `DeliberationResponse` | Validates decision ∈ {REFUTE, RESEARCH, PASS}, amount ≥ 0 |

**Validation failures reject the round** rather than defaulting to 0.5/0.5, eliminating "Shadow Ties" that biased the economy.

## Future Evolution

**Implemented:**
- ✅ Contract-Based Models (Pydantic) — Structured extraction for LLM responses
- ✅ Phase-Based Round Architecture — Decomposed into discrete, testable phases
- ✅ Protocol Interfaces — Explicit contracts for backends/judges
- ✅ Phase Invariant Assertions — Postcondition checks in round phases
- ✅ Dynamic Round Duration — Debates continue until mutual PASS
- ✅ Observational Models — MetricsObserver and ScribeObserver for analytics
- ✅ Split Pot / Initial Bounty — Configurable early payout after initial judgment
- ✅ Deliberation Token Costs — Debaters pay for "thinking" LLM calls
- ✅ YAML Configuration System — Per-model specs for debaters/judges
- ✅ Mixed Model Support — Different models for each participant
- ✅ Ensemble Judging — Multiple judges with weighted averaging
- ✅ **Tool Use (ResearchTool)** — Web search via DuckDuckGo with dynamic token cost
- ✅ **Internal Reasoning (`<thinking>` tags)** — Chain-of-thought hidden from judge/opponent
- ✅ **Self-Summarization Memory** — Bounded context compression for long debates
- ✅ **Positional Bias Mitigation** — Randomized argument order for judges
- ✅ **Async Parallel Generation** — Concurrent initial arguments via asyncio

**Roadmap (in priority order):**

1. **Ground Truth Calibration** [FUTURE]
   - Factual topics where correctness can be verified post-debate

2. **Tiered Arenas** [FUTURE]
   - ELO-like ranking with promotion/relegation
   - Requires question generation system for scale

7. **Reputation System** [FUTURE]
   - Long-term tracking of debater performance across tournaments

8. **Bankruptcy Mechanics** [FUTURE]
   - What happens when a debater hits the debt limit?

