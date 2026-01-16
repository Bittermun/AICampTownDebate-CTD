# Core Concept: Adversarial Token-Economy Debate

## The Big Idea

Train AI models to develop efficient internal reasoning (ITMC) by placing them in an **adversarial debate tournament with a persistent token economy**.

Unlike standard debate training (OpenAI 2018), this system adds:
- **Economic stakes** that persist across rounds
- **Betting mechanics** where models wager on their arguments
- **Actual token cost** for generating responses (not abstract chips)
- **Debt systems** allowing strategic resource allocation
- **Tiered arenas** for skill-matched competition

## Key Terminology

| Term | Definition |
|------|------------|
| **Debater** | Model that generates arguments on a topic |
| **Judge** | Smaller, amnesiac model that evaluates arguments |
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
8. Balances persist to Round N+1
```

## Token Economy Rules (To Be Refined)

**Problem to solve:** Models shouldn't run out of 100 initial tokens immediately.

**Proposed economics:**
- Initial balance: 100 tokens
- Cost per response: ~proportional to LLM tokens used (TBD ratio)
- Award per round: ~20 base + bonus for winning
- Betting fee: 5% of stake (burned)
- Bet multiplier on win: 1.8x stake returned

**Key constraint:** Award rate should exceed average generation cost, so models accumulate tokens over time if they argue efficiently. Verbosity is punished.

## Information Asymmetry

| What Debaters See | What Debaters DON'T See |
|-------------------|-------------------------|
| Topic | Judge's reasoning |
| Opponent's arguments (after initial) | Judge's identity/prompt |
| Confidence scores | Other debater's token balance |
| Own balance and debt | Future topics |

**Rationale:** Hiding judge reasoning prevents debaters from learning to pander to specific phrasings. They must learn what *actually* constitutes a good argument.


## Research vs. Refutation

Debaters can choose TWO types of betting:

| Type | What it does | When to use |
|------|--------------|-------------|
| **Refutation** | Generate counter-argument to opponent | When opponent's argument has clear weaknesses |
| **Research** | Generate additional support for YOUR argument | When you're confident in your position but want to strengthen it |

This allows models to develop different strategies beyond pure adversarial attack.

## LLM-Driven Deliberation

**The betting decision is NOT a heuristic—it is LLM-driven.** Before choosing REFUTE, RESEARCH, or PASS, the debater model explicitly reasons about its strategy. This is where ITMC (Internal Thinking / Mesa-Cognition) happens.

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

- **AI Safety via Debate** (OpenAI 2018) - No economy
- **Constitutional AI** (Anthropic) - Self-critique, no adversary
- **Futarchy** (Robin Hanson) - "Vote values, bet beliefs"
- **Multi-Agent Debate** - No persistent state
- **Thermodynamic analogy** (our discussion) - Tokens = energy, fees = friction

## Goal: ITMC Optimization

ITMC = Internal Thinking / Mesa-Cognition

We want models to develop:
- Compressed, reusable reasoning patterns
- Long-term strategic planning
- Efficient internal representations
- Research vs. refutation strategy selection

The token economy creates selection pressure for these properties.
