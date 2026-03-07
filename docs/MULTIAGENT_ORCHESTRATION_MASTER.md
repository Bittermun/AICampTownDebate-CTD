# Multi-Agent Orchestration Master

## Objective
Run `CODEX_QUEUE.md` with high throughput and low rework using strict gate control, parallel workers, and independent verification.

## Control Plane
- `Queue Lead`: opens/closes gates, schedules tasks, enforces blocked order.
- `Worker`: owns one task file set only, produces handoff with verify output.
- `Gate Verifier`: reruns verify commands independently and accepts/rejects handoffs.
- `Scribe`: updates queue/run status after verifier acceptance.

## Gate Model
- `Gate A`: `TASK-001` only.
- `Gate B`: `TASK-002`, `TASK-003`, `TASK-004`, `TASK-005`, `TASK-006` in parallel after A passes.
- `Gate C`: `TASK-007`, `TASK-008`, `TASK-009`, `TASK-010` in parallel after B passes.
- `Gate D`: `TASK-011`, `TASK-012` in parallel after C passes.
- Any verify failure relocks that task and keeps next gate closed.

## Worker Contract
- Only edit files listed in that task spec.
- Paste raw verify output.
- Declare unresolved ambiguity instead of guessing.
- Do not mark done; verifier marks done.

## Handoff Contract
Each task must create one handoff file:
- `runs/<run_id>/handoffs/TASK-XXX.md`

Required fields:
- `owner`
- `batch`
- `changed_files`
- `spec_compliance`
- `verify_commands`
- `verify_raw_output`
- `blocked_rules_check`
- `risks`
- `unlocks`

## Known Blockers To Resolve Early
- `TASK-004` file-scope conflict vs import blast radius in non-listed files.
- `TASK-004` verify command uses shell pattern that is not PowerShell-safe.
- `tournament_rounds` uniqueness semantics are potentially contradictory.
- `fail_round(reason)` storage contract is underspecified.

## Execution Rhythm
- Progress heartbeat every 20-30 minutes.
- Gate review immediately when the last task in a gate lands.
- Batch-close smoke rerun by verifier before opening next gate.

## Operational Rule
Optimize for correctness of gate transitions, not speed of isolated task completion.
