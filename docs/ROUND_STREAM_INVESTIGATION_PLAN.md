# Round Stream Viewer: Investigation Plan

## Scope
Design and validate a "single tournament round" streaming visual that is easy to run manually.

Date validated: March 6, 2026.

## Current State
- UI/server exists at `scripts/round_stream_viewer.py`.
- Manual launcher exists at `scripts/run_round_stream_viewer.ps1`.
- Current mode is replay-based streaming from a saved transcript (`*_transcript.json`), not live hooks into an active round engine.

## Verification Evidence
The viewer was verified by starting the server and probing both endpoints:
- `/` returned HTTP 200 and expected HTML markers (`Round Stream Viewer`).
- `/events` returned SSE `data:` lines including `round_start`.

Observed results:
- `STATUS=200`
- `HAS_TITLE=True`
- `SSE_DATA_LINES=4` (within first read window)
- First event type: `round_start`

This confirms the visual stream works end-to-end in replay mode.

## Architecture: Current vs Target

Current (working)
- Source: transcript JSON round turns.
- Transport: SSE endpoint replaying turns with timed delays.
- Client: single-page UI with score bars, event log, winner banner, replay button.

Target (optional upgrade)
- Source: live round execution events from `DynamicDebateRound`.
- Transport: same SSE contract, but fed by a runtime event queue.
- Client: unchanged (reuse existing UI contract).

## Gaps To Investigate
- No native live event emitter in `src/arena/dynamic_round.py`.
- Event schema is implicit; needs explicit contract/versioning.
- No durability/replay store for in-progress live streams.
- Background launch reliability on Windows shells needs a hardened wrapper strategy.

## Prioritized Backlog

1. `S` Define event contract and freeze v1 schema
- Add a small typed event model and examples for `round_start`, `turn`, `judgment`, `round_end`, `error`.

2. `S` Add launch hardening
- Improve `run_round_stream_viewer.ps1` with startup checks, friendly failures, and port-in-use handling.

3. `M` Add live emitter hook in `DynamicDebateRound`
- Add optional callback/event sink called at key lifecycle points without affecting scoring logic.

4. `M` Build live bridge process
- Minimal server subscribes to runtime events and serves `/events` and `/`.

5. `M` Add reconnect support
- Track event IDs and support resume (`Last-Event-ID`) for dropped clients.

6. `L` Add operator mode
- Add small controls: pause/replay, speed, and round selector from available logs/live rounds.

## Recommended Implementation Order
1. Event contract v1
2. Launcher hardening
3. Live emitter hook
4. Live bridge
5. Reconnect support

## Success Criteria
- One command starts viewer and opens browser.
- Viewer reliably shows one full round from transcript replay.
- Optional live mode streams an active round with same UI and no scoring regressions.
