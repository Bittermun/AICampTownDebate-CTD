# Multi-Agent Execution Protocol (2026-03-05)

Purpose: run 3 parallel AI contributors without merge collisions, while preserving trust-first evaluation standards.

## 1) Workstream Ownership (Hard Boundaries)

### Agent A: Trust/Governance Foundation (Phases 0-6 owner)
Primary scope:
- `docs/EVALUATION_CONTRACT.md`
- `docs/BENCHMARK_PROTOCOL.md`
- `docs/NEXT_AI_BOOTSTRAP.md`
- `configs/benchmark_phase1.yaml`
- `scripts/audit_score_ceiling.py`
- `scripts/reconcile_settlement.py`
- `src/benchmark/scoring.py`
- `src/benchmark/config_models.py`
- `src/benchmark/registry.py`

Responsibility:
- Claim-level enforcement (`L0/L1/L2`)
- Governance checks promoted from docs to executable pass/fail behavior
- Statistical and reproducibility hardening policy

### Agent B: Durable Orchestration / Resume Reliability
Primary scope:
- `scripts/run_phase1_batch.py`
- `scripts/run_tournament_batch.py`
- `tests/test_phase1_batch_endpoint_assignment.py`
- `tests/test_run_tournament_batch_resume.py`
- `src/benchmark/batch_utils.py`

Responsibility:
- Resume correctness
- Checkpoint consistency and stale-row repair
- Fatal failure propagation and deterministic re-runs

### Agent C (Codex): Feature Sandbox + Comparative Evaluation
Primary scope:
- `src/models/debater.py`
- `src/config_loader.py`
- `demo_tournament.py`
- `demo_dynamic.py`
- `configs/multi_agent_experimental.yaml`
- `tests/test_debater_multi_agent.py`
- `tests/test_benchmark_config_parse.py` (feature knobs only)
- `README.md`
- `docs/PROCEDURES.md`

Responsibility:
- Experimental multi-agent behavior (config-gated)
- Strictly controlled on/off comparisons
- No claim-level policy edits

## 2) Shared File Rules (Collision Prevention)

Shared-hot files:
- `src/benchmark/runner.py`
- `DEVLOG.md`
- `AGENT_FORUM.md`
- `scripts/check_agent_ownership.py`

Rules:
1. `src/benchmark/runner.py` has single-writer lock per day.
2. `DEVLOG.md` and `AGENT_FORUM.md` append-only; never rewrite previous entries.
3. If two agents need the same file in one day, the second agent waits for lock release and rebases mentally on latest file contents before editing.

## 3) Merge Order and Gates

Order (must be respected):
1. Governance foundation (Agent A)
2. Resume reliability (Agent B)
3. Feature experiments (Agent C)

Gate to merge Agent C feature work:
- No failing governance checks introduced.
- No breakage in resume tests.
- Feature remains default-off unless explicitly selected by config.

## 4) Two-Sprint Plan

Sprint 1 (2026-03-05 to 2026-03-11): Trust + Reliability Lock

Agent A deliverables:
- Executable claim-safety freeze (default L1 unless strict criteria pass).
- Governance checks wired to fail CI/summary status.

Agent B deliverables:
- Resume behavior verified in both benchmark and tournament batch paths.
- Exception-to-record behavior confirmed in manifests.

Agent C deliverables:
- Multi-agent injection remains experimental and config-gated.
- Add on/off comparison script or report section (feature impact vs cost).

Sprint 1 exit criteria:
- Claim status cannot be over-promoted by accident.
- Interrupted runs can resume without duplicate execution.
- Feature experiments cannot bypass trust gates.

Sprint 2 (2026-03-12 to 2026-03-18): Measurement Truth + Statistical Hardening

Agent A deliverables:
- Objective/model-derived scoring path promoted for key groups.
- Seed minimum + CI/effect-size policy enforced.

Agent B deliverables:
- Batch manifests include complete replay metadata for reproducibility.
- Deterministic resume behavior validated across repeated resume cycles.

Agent C deliverables:
- Multi-agent mode benchmarked on fixed matrix:
  - `full system`
  - `stripped emergent`
  - `baseline_no_econ`
  - `multi_agent_on_off`

Sprint 2 exit criteria:
- Objective signal dominates fixture-only proxy for claim-bearing metrics.
- Statistical confidence is explicit in summaries.
- Multi-agent uplift is reported with cost/latency tradeoff.

## 5) Daily Sync Template (Required)

Each agent posts once per day to `AGENT_FORUM.md`:
- `Touched files`
- `Behavior change`
- `Evidence/tests run`
- `Open risks/blockers`

If touching a shared-hot file, include:
- `Lock acquired at <timestamp>`
- `Lock released at <timestamp>`

## 6) Scope Enforcement Command

Use `scripts/check_agent_ownership.py` in two phases:

Early iteration (non-blocking warning):

```bash
python scripts/check_agent_ownership.py --agent C --mode warn --files src/models/debater.py src/config_loader.py demo_tournament.py
```

End-of-sprint / pre-merge (blocking gate):

```bash
python scripts/check_agent_ownership.py --agent C --mode gate --use-git-status
```

Notes:
- Prefer `--files` in a shared dirty tree so agents only validate their intended patch set.
- `--use-git-status` is stricter and should be used in isolated branch/worktree or final gate.
- Shared files are allowed but require lock-note protocol in `AGENT_FORUM.md`.

## 7) Immediate Execution Checklist (Today)

1. Adopt this ownership map as active policy.
2. Keep Agent A as owner of claim-level/gov files this sprint.
3. Keep Agent B as owner of batch/resume scripts and tests.
4. Keep Agent C limited to feature sandbox and comparative outputs.
5. Defer cross-owner edits unless they are blocker fixes; if blocker, log in `AGENT_FORUM.md` before editing.

---

This protocol is intentionally strict for Sprint 1. Relax only after trust and resume foundations are green.
