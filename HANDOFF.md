# 🚀 AI Token-Debate Experiment: Agent Handoff

Welcome to the project. You are picking up after a major strategic pivot (Session 22).

This file is your entry point. Read the documents below in order to understand the philosophy, history, and what you are being asked to build.

## 📚 Required Reading (Do not skip)

1. **`CONCEPT.md`**
   - Read this first. Understand the philosophy: *Emergent over Prescribed*. We are building an economic environment to select for efficient dialectical reasoning (collaborative truth-seeking), not a game to force adversarial behavior.
2. **`AGENT_FORUM.md`**
   - Read this second. It contains hard-won lessons from the last 20 sessions by previous agents, including critical warnings about API signatures, Windows encoding, and the dangers of arbitrary game mechanics.
3. **`DEVLOG.md`**
   - Read the last three entries (Sessions 20, 21, 22). This covers the most recent implementations: the "Wallet Phase" architecture, the health-check observers, and the underlying mathematical goals.
4. **`docs/ECONOMIC_ANALYSIS.md`**
   - Read this to understand the fundamental math of the experiment (Kelly Criterion, Expected Value). This is the blueprint for de-arbitrarifying the system.

## 🏗️ Current Architecture State

- **Round Logic**: `src/arena/dynamic_round.py` executes a loop of phases (Arguments -> Judge -> Deliberation -> Judge Revision). The round terminates organically when both debaters choose to PASS due to low token balances (Dynamic Duration).
- **The Wallet Phase**: Debaters must explicitly state a `max_budget` in their private deliberation JSON. This `max_budget` mathematically limits the `max_tokens` of their subsequent generation.
- **The Engine**: We are currently running 1.5b and 7b models via local Ollama for rapid iteration.
- **Pre-Tournament Diagnostics**: `HealthCheckObserver` watches for pathological problems (all-passes, validation failures) without blocking the core round loop.

## 🚧 Next Priorities: The Dialectical Leverage Points

Previous agents drifted into planning complex game mechanics (AI banks, stance forcing, oracles). The user has explicitly rejected this approach in favor of foundational science and measurement. 

Your job is to implement these three non-arbitrary leverage points:

### 1. The Dependent Variable: Measuring Reasoning Trajectories
We currently have no way to prove a model's thinking improves over a tournament.
- **The Task:** Build an analytical tool/script that parses the `<thinking>` traces across multiple transcribed rounds. We need to measure if economic pressure creates structured, compressed, or synthesized internal reasoning (e.g., measuring thinking tag length variance, unique concept repetition, or strategy shifts).

### 2. The Bottleneck: Calibrating the Judge for Dialectics
If the judge's scoring variance is too high, the economic signal is purely random noise, and the models will learn nothing.
- **The Task:** Write a stress-testing script (`tests/stress_judge_variance.py`) that feeds the *exact same argument* through the Judge 10 times to measure its variance. Furthermore, tune the `MultiDimensionJudgment` prompt (in `judge_prompts.py`) to explicitly punish *obstinacy* (ignoring valid counter-points) and reward *synthesis* (acknowledging and integrating them).

### 3. The Math: Anchoring the Economics
The current economy runs on arbitrary numbers (e.g., initial balance 200, fee 5%).
- **The Task:** De-arbitrarify the runway using math. Make one philosophical decision with the user: "A model must survive N rounds of losing before bankruptcy to have space to adapt." From that *one* invariant, use the Expected Value and Kelly criterion formulas in `ECONOMIC_ANALYSIS.md` to mathematically derive the Initial Balance, the Pot Size, and the Fee Rate. Replace the guesswork in `tournament_config.yaml` with derived settings.
