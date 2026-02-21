# AI Token-Debate Experiment: Agent Handoff (Current)

This file is a fast orientation for contributors joining after Sessions 23-24 (2026-02-21).

## Required Reading

1. `CONCEPT.md`
   - Core philosophy and current decision model (`RESPOND/PASS`, wallet budgeting).
2. `DEVLOG.md`
   - Read newest entries first (Sessions 24 and 23), then Session 21/20 for background.
3. `AGENT_FORUM.md`
   - Prior strategic discussion and implementation pitfalls.
4. `docs/ECONOMIC_ANALYSIS.md`
   - Current economics assumptions, formulas, and calibration workflow.
5. `docs/PROCEDURES.md`
   - Reproducible strict-run process and artifact expectations.

## Current Architecture State

- Round loop: `src/arena/dynamic_round.py`
  - Initial generation -> initial judgment -> iterative deliberation/generation/judgment -> final distribution.
- Wallet phase: `max_budget` chosen in deliberation and enforced as generation token cap.
- Decision schema: `RESPOND` or `PASS` (`use_search` optional inside `RESPOND`).
- Judging: single/ensemble/consensus supported in `src/models/judge.py`.
- Runtime guardrails: strict preflight + optional judge variance gate in `demo_tournament.py`.
- Analysis tooling: selection health dashboard + trajectory parser under `src/analysis/`.

## Project Direction

- Primary objective is evidence quality, not adding arbitrary mechanics.
- Theoretical lens combines economics (allocation under scarcity), evolution (selection over policies), and thermodynamics (token accounting and friction).
- Strong preference: improve incentives and measurement before adding new game rules.

## Expectations for New Work

- Keep experiments config-driven (`configs/*.yaml`).
- Use strict mode for research claims; reserve `--allow-stub` for plumbing.
- Treat single-run outcomes as directional only; report repeated-run behavior.
- Maintain `DEVLOG.md` with concrete decisions and rationale.

## Active Priorities

1. Strengthen reasoning-trajectory evidence
   - Use and refine `src/analysis/trajectory_parser.py` on real tournament artifacts.
2. Keep judge signal reliable
   - Continue variance gating and prompt tuning where needed.
3. Keep economics non-arbitrary
   - Calibrate parameters from explicit runway/adaptation goals, not ad hoc tuning.
4. Resolve known semantic drift
   - Keep docs synchronized with runtime behavior, especially around debt/elimination semantics.

## Practical Notes

- Windows environment is common; keep output ASCII-safe.
- Validate quickly with targeted scripts before long tournament runs.
- Prefer reproducible artifacts in `logs/` for every claim.
