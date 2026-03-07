# Architecture Decision Records (ADRs)
# AIcamptowndebate — persistent AI debate league

Each ADR records a decision that was made, WHY it was made, and what was rejected.
These are permanent records. Superseded decisions get a "Superseded by" line, not deletion.

---

## ADR-001: PostgreSQL as primary database (SQLite for local dev)

**Status:** Accepted 2026-03-06

**Context:**
The project started storing tournament results as JSON files per run. As tournament count grew (200+
runs), finding, aggregating, and resuming across runs became painful. We need: multi-tournament
leaderboards, temporal replay, crash-resumption, and eventually public access.

**Decision:**
Postgres for production. SQLite for local dev and CI (same schema, dialect differences handled
by schema_sqlite.sql). No MongoDB, no Redis, no document stores.

**Rationale:**
- Tournament data is relational: agents → tournaments → rounds → judge_scores (foreign keys matter)
- We need transactional guarantees when updating agent career stats (ACID)
- Postgres JSONB gives flexibility for config_json without losing query ability
- SQLite parity keeps the dev loop instant (no Docker required to run a test)
- Redis rejected: no persistence guarantee without extra config; we don't need sub-ms latency
- MongoDB rejected: schema enforcement matters more than schema flexibility here

**Consequences:**
- Codex tasks must ship both schema.sql (Postgres) and schema_sqlite.sql
- BRIN indexes are Postgres-only; SQLite version omits them
- psycopg2 is a production dep; sqlite3 is stdlib

---

## ADR-002: No ORM — raw SQL only (psycopg2 / sqlite3)

**Status:** Accepted 2026-03-06

**Context:**
Several contributors suggested SQLAlchemy or Django ORM for faster development.

**Decision:**
Raw SQL + psycopg2 for Postgres, sqlite3 for SQLite. No ORM layer.

**Rationale:**
- The query layer is small (12 functions in ops.py). ORM complexity > benefit at this scale.
- ORMs hide query plans. For a performance-sensitive leaderboard, we need to see what SQL runs.
- The schema is write-once stable — no migrations needed during initial build sprint.
- Codex agents write simpler, more verifiable code without ORM magic.
- If scale demands it, we can add SQLAlchemy Core (not ORM) later without rewriting business logic.

**Consequences:**
- ops.py functions are verbose but readable
- SQL injection risk mitigated by parameterized queries (always use `?` / `%s`, never f-strings in SQL)

---

## ADR-003: Single provider backend (OpenAI-compatible), eliminate Ollama and vLLM

**Status:** Accepted 2026-03-06

**Context:**
The codebase had three backends: ollama_backend.py, vllm_backend.py, openai_compat_backend.py.
Each added a branching path through debater.py and judge.py, doubling the test surface for no
empirical benefit — all production runs already used Groq via openai_compat.

**Decision:**
Delete ollama_backend.py and vllm_backend.py. Rename openai_compat_backend.py → provider_backend.py
with class rename OpenAICompatBackend → ProviderBackend.

**Rationale:**
- "You aren't gonna need it" — Ollama/vLLM have never been used in a real campaign run
- Every branch is a maintenance burden and a test failure vector
- OpenAI-compat protocol is the de facto standard; any provider (Groq, Together, local vLLM, Ollama
  with openai-compat mode) can be reached through a single base_url + api_key pair
- Provider diversity is now a config concern (DB row in provider_configs), not a code concern

**Rejected alternatives:**
- Keep all three: rejected — dead code is a liability, not an asset
- Keep vLLM only for local: rejected — same protocol, just set base_url=localhost

**Consequences:**
- Any model reachable via /v1/chat/completions works (Groq, Together, OpenRouter, local vLLM)
- stub: backend retained for all tests (no network required for CI)

---

## ADR-004: Agent state (tiny, mutable, ACID) separated from round traces (large, append-only)

**Status:** Accepted 2026-03-06

**Context:**
Initial design considered a single "agent_runs" table combining career state + per-round data.
Outside AI reviewer flagged this as a dangerous coupling.

**Decision:**
Two distinct storage patterns:
- `agents` table: tiny, mutable, ACID transactions for career_wins, career_roi, current_balance
- `tournament_rounds` table: append-only, no UPDATE on completed rows, JSONB transcript

**Rationale:**
- Agent career state changes infrequently and must be atomic (wins+losses+roi update together)
- Round transcripts are immutable after completion — append-only gives crash safety for free
- Keeping them separate allows different backup/archival strategies
- Leaderboard queries hit agents (tiny) not tournament_rounds (large)
- agent_state_snapshots provides temporal replay without polluting the live agent row

**Consequences:**
- RoundWriter.complete_round() updates tournament_rounds; caller must separately update agents
- Snapshots are taken manually (patch apply, tournament end) — never per-round automatically

---

## ADR-005: Idempotency keys (UUID) on every round

**Status:** Accepted 2026-03-06

**Context:**
The arena crashes mid-tournament. On restart, it doesn't know which rounds ran, which are
currently running (and will complete), and which genuinely failed.

**Decision:**
Every round row has a UUID `idempotency_key` (UNIQUE). begin_round() returns the key.
On retry, caller checks if the key exists with status=completed before running again.

**Rationale:**
- UUID generated before the API call → if the API call succeeds but the write fails, retry
  with the same key will detect the completed round and skip re-execution
- UNIQUE constraint at DB level makes double-execution impossible
- mark_stale_rounds_dead() handles the "running but orphaned" case (timeout after 5 min)

**Consequences:**
- begin_round() must be called before the API call, not after
- Callers must handle "key already exists" as a normal case, not an error

---

## ADR-006: Patch notification system (agents notified of rule changes like game patch notes)

**Status:** Accepted 2026-03-06

**Context:**
Tournament rules change between campaigns (economy pot 40→200, judge model change, prompt update).
Under the old design, agents ran with stale expectations — the economy had changed but they didn't
know. This contributed to irrational-seeming behavior.

**Decision:**
Immutable `patches` table. Each agent row has `last_patch_applied`. When an agent runs in a
tournament, apply_patch_notification() compares agent's patch version to current patch. If behind,
inject the delta as a prefix to their system prompt: "PATCH NOTES since your last run..."

**Rationale:**
- Game analogy: players read patch notes before ranked matches. Agents should too.
- Agents reasoning about economy are sensitive to pot size, judge identity — they should know when
  these change
- Immutable patch log gives us a full audit trail of when rules changed and which runs used which rules
- Outside-game analogy: it's a contract update. Consent requires notification.

**Rejected:**
- Baking patch info into YAML config: rejected — YAML is per-run, not persistent across agent history
- Ignoring patch deltas: rejected — agent behavior that was rational under v1.0 may be wrong under v1.2

**Consequences:**
- register_patch.py must be run before any tournament that uses new rules
- Patch version must be present on every tournament_rounds row (for impact analysis)

---

## ADR-007: Round traces are append-only; completed rows are never updated

**Status:** Accepted 2026-03-06

**Context:**
Early design updated round rows with judge scores after they were written.

**Decision:**
Once status=completed, a round row is never updated. All data (transcript, scores, roi) must be
written in the complete_round() call. fail_round() only updates status and retry_count.

**Rationale:**
- Append-only is crash-safe: partial writes leave the row in 'running' or 'failed', never corrupted
- Forensics: if a judge score is wrong, we see exactly what was written at completion time
- Aligns with event sourcing principles — past events don't change

**Consequences:**
- transcript_json and judge_scores must be computed before complete_round() is called
- No "fix-up" queries allowed; if scores are wrong, create a new round row with corrected data

---

## ADR-008: Token economy — pot=200, Kelly criterion, EV-guard

**Status:** Accepted 2026-03-06 (replaces original pot=40 design)

**Context:**
Original economy: pot=40 tokens per round, argument cost ~62.7 tokens average. This made
arguing always EV-negative. Models universally held (pass_rate=0.83) — not from strategy, but
from correct expected-value math. 200 prior runs of data are contaminated by this.

**Decision:**
- pot=200 tokens per round (above 62.7 cost → EV-positive to argue)
- Kelly criterion bet sizing: kelly_scale=0.5, kelly_cap=0.25 (half-Kelly, conservative)
- EV-guard: reject bets with EV < -0.03 (don't bet when you know you'll probably lose)
- Deliberation prompt v2: explicit cost ratio (1 balance = 20 LLM tokens), deliberation cost disclosed

**Rationale:**
- Models are rational. If arguing is EV-negative, they won't argue — and shouldn't. Fix the incentive.
- Kelly criterion is the theoretically optimal bet sizing under uncertainty with log-utility
- EV-guard prevents emotionally-driven overbetting (which LLMs sometimes do without guardrails)
- Disclosing deliberation cost in prompt makes the economic context complete — no hidden costs

**Evidence:**
- clean_100 campaign (n=99): pass_rate=0.491, alpha_win_rate=54% (was 70-80%)
- Probe on qwen2.5:7b: 100% accuracy on EV-reasoning scenarios under new economy

**Non-arbitrariness note:**
Every mechanism here has an economic or information-theoretic grounding. Nothing is a hand-tuned rule.
Kelly criterion is derived from maximizing log(wealth). EV-guard is a standard options trading filter.
The cost ratio is an empirical measurement (average LLM token cost per argument), not a chosen number.

---

## ADR-009: Behavioral directives are NOT the path to emergent behavior

**Status:** Accepted 2026-03-06

**Context:**
veteran_quick experiments added hand-written behavioral directives to system prompts:
SURVIVAL_FIRST, ADAPT_ON_LOSS, PUNISH_WEAKNESS, ANTI_RAMBLE. This was identified as wrong.

**Decision:**
Emergent behavior comes from incentive design, not explicit instructions. Directives are banned
from the emergent-track experiments. Economic guardrails (Kelly, EV-guard) are allowed because
they are mechanism constraints, not behavioral instructions.

**Rationale:**
- If you tell a model "ADAPT_ON_LOSS: diagnose what failed," you are not observing adaptation —
  you are observing instruction-following. These are different phenomena.
- The goal is to see what strategic behaviors emerge from economic pressure alone.
- Hand-written directives also introduce arbitrariness: why these 4? why this wording?
- Kelly + EV-guard are structural constraints (like market rules), not behavioral coaching.

**Consequences:**
- clean_veteran configs should use Kelly + EV-guard only, zero system_prompt behavioral content
- veteran_quick data (n=20) is valid for testing directive effects but NOT for measuring emergence
- Future experiments: directive track vs emergent track as parallel treatment groups

---

*Last updated: 2026-03-06 | Maintainer: see AGENT_FORUM.md for multi-agent authorship*
