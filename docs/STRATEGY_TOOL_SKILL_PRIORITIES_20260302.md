# Strategy: Idea Backlog + Tool/Skill Priorities (2026-03-02)

This note records the high-impact ideas from the broad sweep and turns them into a practical execution plan for this repo.

## 1) Recorded Idea Backlog (GitHub-Inspired)

Priority order is based on expected impact on claim quality, not novelty.

1. **Model-derived benchmark scoring (replace fixture-ceiling dependence)**
   - Wire benchmark scoring to real task evaluators rather than static fixture `metric_values`.
   - Candidate integrations: `lm-evaluation-harness` style adapters for objective datasets.
   - Why first: removes score-ceiling bottleneck and unlocks true L2 quality claims.

2. **Uncertainty-aware ranking (Bradley-Terry + bootstrap CIs)**
   - Keep Elo if needed, but add pairwise strength estimates and confidence intervals.
   - Use uncertainty to drive matchup selection.
   - Why second: makes leaderboard decisions statistically grounded.

3. **Population tournament scheduling (Swiss/challenger queues)**
   - Move from fixed A/B flow to multi-model pools with information-efficient pairing.
   - Why third: more signal per run budget, better scaling for model variants.

4. **Evolution loop for policy variants**
   - Mutate prompts/rule-cards/bet knobs, run mini-tournaments, keep top variants.
   - Why fourth: turns existing trajectory logs into a systematic search engine.

5. **Execution-grounded judging for objective tasks**
   - For checkable tasks, add verify/execute scoring paths to reduce judge-only noise.
   - Why fifth: improves reliability of correctness metrics.

6. **Continuous adversarial regression gates**
   - Add red-team probes as hard gates before promoting variants/champions.
   - Why sixth: prevents brittle gains from slipping into registry updates.

7. **Conditional/sliced leaderboards**
   - Track performance by topic/prompt family, not only single aggregate.
   - Why seventh: exposes hidden weaknesses and specialization.

8. **Trace observability**
   - Add per-step traces for deliberation cost, search usage, and judge drift.
   - Why eighth: lowers debugging and tuning cycle time.

## 2) Tool Prioritization (What to Use First)

Use tools in this order unless a task explicitly requires otherwise:

1. **Local code + tests (primary)**
   - Use `rg`, targeted unit tests, and existing scripts in `tests/` + `scripts/`.
   - Best for fast iteration, minimal risk, and reproducible artifacts.

2. **Existing benchmark pipeline hooks**
   - Extend `src/benchmark/*` and policy/config models before adding new infra.
   - Keeps changes aligned with existing evidence contract.

3. **External integrations (secondary)**
   - Bring in outside evaluators/ranking methods only after local interfaces are stable.
   - Minimize premature dependency complexity.

4. **Automation/UI tooling (only when needed)**
   - Browser automation is lower priority unless we add dashboard workflows that require it.

## 3) Skill Prioritization (From AGENTS.md)

Available skills this session:
- `playwright`
- `skill-creator`
- `skill-installer`

Recommended priority:

1. **No skill by default for core roadmap execution**
   - Current roadmap is mostly Python architecture + eval mechanics.
   - Shell + code edits + tests are enough for most work.

2. **Use `playwright` only for UI-specific tasks**
   - Example: if we add a web dashboard and need end-to-end flow checks/screenshots.

3. **Use `skill-creator` after process stabilizes**
   - Create a custom local skill once repeated workflows are clear.
   - Best candidate: a dedicated `benchmark-governance` skill for strict runs, artifacts, and claim checks.

4. **Use `skill-installer` only if a missing capability blocks progress**
   - Example: if we need a curated skill for a repeat external integration workflow.

## 4) Execution Approach (Phased)

### Phase A: Measurement truth first (highest leverage)
- Goal: eliminate fixture-ceiling as primary blocker.
- Steps:
  1. Add model-derived scoring path in `src/benchmark/runner.py` + `src/benchmark/scoring.py`.
  2. Mark provenance explicitly in outputs (`model_derived` vs `fixture_static`).
  3. Add tests proving aggregate score changes with model output changes.

### Phase B: Ranking validity
- Goal: make league movement statistically meaningful.
- Steps:
  1. Extend `src/benchmark/registry.py` with uncertainty-aware ranking outputs.
  2. Keep backward-compatible Elo fields while adding CI fields.
  3. Add promotion policy checks that require uncertainty thresholds.

### Phase C: Population scaling
- Goal: increase data efficiency per run.
- Steps:
  1. Add Swiss/challenger matchmaking module.
  2. Support >2 participants in tournament orchestration.
  3. Add scheduling tests for fairness and repeatability.

### Phase D: Policy search + hardening
- Goal: sustained improvement without regressions.
- Steps:
  1. Add controlled prompt/rule-card mutation runner.
  2. Add adversarial probe gate in promotion path.
  3. Add trace analytics for quick failure diagnosis.

## 5) Suggested Immediate Next Action

Start with **Phase A, Step 1** in a small PR:
- Introduce a `score_source` abstraction in benchmark scoring.
- Keep current fixture path as fallback.
- Add one model-derived metric end-to-end as a proof of integration.

