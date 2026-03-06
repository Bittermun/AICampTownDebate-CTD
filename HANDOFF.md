# AI Token-Debate Experiment: Agent Handoff

Fast orientation for contributors joining after Session 25 (2026-03-05).

## Required Reading

1. `CONCEPT.md` — Goals, design philosophy, and current decision model.
2. `docs/PROJECT_STATUS.md` — Honest readiness scores, known bugs, dead code, gap analysis.
3. `DEVLOG.md` — Read newest entries first (Sessions 25, 24, 23).
4. `AGENT_FORUM.md` — Multi-agent strategic discussion, campaign results, and implementation lessons.
5. `docs/ECONOMIC_ANALYSIS.md` — Economy math, calibration workflow, and parameter profiles.
6. `docs/PROCEDURES.md` — Reproducible run procedures and artifact expectations.

## Current Architecture (Verified Against Code)

### Active Code Paths

- **Round loop:** `src/arena/dynamic_round.py` — generate args, judge, iterate (deliberate/bet/respond/judge), distribute tokens, audit accounting.
- **Debater:** `src/models/debater.py` — backend dispatch, `<thinking>` extraction, Kelly-sized betting via `decide_bet()`, wallet phase budget authorization, multi-agent peer draft injection.
- **Judge:** `src/models/judge.py` — `LLMJudge`, `EnsembleJudge`, `ConsensusJudge`. Multi-dimension scoring (accuracy/responsiveness/development). Positional bias mitigation via argument order randomization.
- **Economy:** `src/economy/ledger.py` (balance tracking), `betting.py` (stake + fee), `distribution.py` (confidence-proportional pot split).
- **Tournament:** `src/arena/tournament.py` — multi-round loop with early stopping (bankruptcy, SPRT delta). Records outcomes to debater memory.
- **Config:** `src/config_loader.py` — YAML with BOM-safe encoding. Produces `TournamentConfig` with nested `DebaterSpec`, `JudgeSpec`, `EconomyConfig`, `RoundConfig`.
- **Transcripts:** `src/logs/transcript.py` — JSON + Markdown export with full deliberation/judgment/payout data.
- **Benchmark:** `src/benchmark/runner.py` — phase-1 benchmark with gate checks, score provenance, claim posture levels (L0/L1/L2).
- **Evolution:** `src/evolution/campaign.py` — mutate strategy profiles, evaluate via tournament, select elites.
- **Memory:** `src/memory/strategy_memory.py` — cross-round playbook injection into deliberation prompts.

### Dead Code (Do Not Use)

- `src/arena/round.py` — old single-pass round, superseded by `DynamicDebateRound`
- `src/models/judge_factory.py` — never imported
- `src/models/protocols.py` — Protocol definitions, never used at runtime
- `Debater.generate_research()` — unreachable from any execution path
- `src/economy/bank.py` — will crash on import (references nonexistent `base_model` module). Both methods are stubs.

### Known Bug

`src/arena/tournament.py:save_results()` — winner-field logic uses `self._eliminated is False` which is never true (value is `None` or a string). Works by accident because it falls through to the balance comparison, which gives the right answer.

## Project Direction

Two goals:

1. **Train a competitive model at lower cost** — use scarcity-selected debate traces as training data for a student model.
2. **Observe emergent strategic behavior** — measure whether economic pressure produces allocation intelligence without explicit instruction.

Core principle: **non-arbitrariness** — every mechanism should be grounded in economics, evolution, or information theory. See `CONCEPT.md` for the full audit.

## Expectations for New Work

- Keep experiments config-driven (`configs/*.yaml`).
- Use strict mode for research claims; reserve `--allow-stub` for plumbing.
- Treat single-run outcomes as directional only; report repeated-run behavior.
- Check `docs/PROJECT_STATUS.md` for known gaps before building on top of something that might be broken.
- Update `DEVLOG.md` with concrete decisions and rationale (newest entries at top).

## Active Priorities

1. **Close the training loop** — generate, fine-tune, evaluate. Currently stops at data generation.
2. **Reduce pass rate** (0.83 observed vs ~0.35 target) through economy pressure tuning, not penalties.
3. **Validate behavioral evidence** — confirm adaptation_gain and economy_awareness signals are robust across seeds.
4. **Judge quality** — use 7b judge minimum for research-grade data (1.5b stdev=0.141 is too noisy).
5. **Commit untracked work** — see `docs/PROJECT_STATUS.md` for the list of important untracked files.

## Practical Notes

- Windows environment. Keep output ASCII-safe (emoji in print causes `UnicodeEncodeError` under subprocess capture).
- Hardware: RTX 4070 Laptop (8GB VRAM). QLoRA on 1.5b fits. 7b is tight.
- Validate quickly with targeted scripts before long tournament runs.
- Prefer reproducible artifacts in `logs/` for every claim.
