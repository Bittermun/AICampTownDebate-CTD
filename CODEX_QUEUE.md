# CODEX QUEUE
# ═══════════════════════════════════════════════════════════════════════════════
# WHAT YOU ARE BUILDING — read this first, every agent, every task
# ═══════════════════════════════════════════════════════════════════════════════
#
# A persistent, resumable, public AI debate league.
# Models compete in token-economy tournaments: arguing costs balance, winning earns it.
# The system runs forever. Tournaments resume after crashes. Agents accumulate career
# history. When rules change (economy, judging, prompts), a "patch" is logged and
# agents are notified like a game patch note.
# Eventually: anyone adds their API key and enters their model.
#
# Current state: research scripts + JSON files. Target state: Postgres-backed,
# provider-agnostic, resumable, observable.
#
# Architecture decisions already made (do not re-decide these):
#   - Postgres primary, SQLite for local dev/test
#   - Single provider backend (openai-compat). Ollama/vLLM deleted.
#   - Agent state (tiny, mutable) separated from round traces (large, append-only)
#   - All resume logic lives in DB, not memory
#   - No ORM. Raw SQL + psycopg2/sqlite3 only.
#
# WHY each decision was made: see docs/DECISIONS.md (ADR-001 through ADR-009)
# Verify all tasks at once: python scripts/verify_all.py [--batch A|B|C|D]
#
# ═══════════════════════════════════════════════════════════════════════════════
# RULES — non-negotiable
# ═══════════════════════════════════════════════════════════════════════════════
# 1. Work tasks in listed order within each batch. Respect blocked status.
# 2. Paste verify output before marking done.
# 3. Ambiguity = post question, do not improvise.
# 4. Do not touch files outside the listed files for each task.
# 5. No ORM, no logging frameworks, no docstrings unless spec asks.
# 6. First line of every new file: # TASK-XXX output — see CODEX_QUEUE.md
# 7. You are a compiler. Architecture decisions come from upstream. Implement only.
#
# ═══════════════════════════════════════════════════════════════════════════════
# BATCH PLAN (for parallel agent scheduling)
# ═══════════════════════════════════════════════════════════════════════════════
#
# BATCH A — 1 agent, must complete before anything else
#   TASK-001: Postgres schema
#
# BATCH B — run all 6 in parallel after TASK-001 passes
#   TASK-002:  DB connection module
#   TASK-003:  Core CRUD ops layer
#   TASK-004A: Rename openai_compat_backend -> provider_backend (low-risk, no deletes)
#   TASK-004B: Delete Ollama/vLLM files, edit debater.py + judge.py (high-risk, do after 004A)
#   TASK-005:  Patch registration script
#   TASK-006:  Agent registry module
#
# NOTE: 004A and 004B are sequential within batch B (004B blocked on 004A).
# All others in batch B are truly parallel.
#
# BATCH C — run all 4 in parallel after BATCH B passes
#   TASK-007: Provider health check
#   TASK-008: Tournament round writer (DB instead of JSON)
#   TASK-009: Resume loader
#   TASK-010: Leaderboard queries
#
# BATCH D — run after BATCH C
#   TASK-011: Config → provider_config bridge
#   TASK-012: JSON log migration (import existing runs into DB)
#   TASK-013: Wire arena to DB writer (dynamic_round.py accepts optional RoundWriter)
#   TASK-014: League entry point (run_league.py — start/resume tournament with DB)
#
# NOTE: TASK-013 and TASK-014 are the "last mile" that makes everything above actually used.
#       Without them the DB layer is complete but never called during tournament execution.
#
# WINDOWS NOTE: All verify commands must be run in Git Bash, not PowerShell.
#   `tail` is not a PowerShell command. Alternatively use: python scripts/verify_all.py
#
# ═══════════════════════════════════════════════════════════════════════════════

---

## TASK-001 [status: ready] [batch: A]
**Title:** Create Postgres schema (SQLite-compatible for local test)

**File:** `src/db/schema.sql`

**Action:** CREATE

**Spec:**

```sql
-- provider_configs: one row per API endpoint a model can be reached at
CREATE TABLE IF NOT EXISTS provider_configs (
    id              TEXT PRIMARY KEY,
    base_url        TEXT NOT NULL,
    api_key         TEXT,
    model_id        TEXT NOT NULL,
    extra_headers   JSONB DEFAULT '{}',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_health_ok  TIMESTAMP
);

-- patches: immutable changelog of every rule/economy/prompt change
CREATE TABLE IF NOT EXISTS patches (
    version             TEXT PRIMARY KEY,
    applied_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description         TEXT NOT NULL,
    config_delta        JSONB DEFAULT '{}',
    affected_components TEXT[] DEFAULT '{}'
);

-- agents: persistent identity + mutable career state (tiny rows, ACID)
CREATE TABLE IF NOT EXISTS agents (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    provider_config_id  TEXT REFERENCES provider_configs(id),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at      TIMESTAMP,
    current_balance     INTEGER DEFAULT 1000,
    career_wins         INTEGER DEFAULT 0,
    career_losses       INTEGER DEFAULT 0,
    career_roi          REAL DEFAULT 0.0,
    specialization_tags JSONB DEFAULT '[]',
    last_patch_applied  TEXT REFERENCES patches(version),
    state_json          JSONB DEFAULT '{}' CHECK(state_json IS NULL OR json_typeof(state_json::json) = 'object')
);

-- agent_state_snapshots: frozen copies for temporal replay/debugging
-- NOTE: snapshots are manual/optional — taken on patch apply or tournament end only.
-- Do NOT snapshot every round. Insert via explicit call, never automatically.
CREATE TABLE IF NOT EXISTS agent_state_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    tournament_id   TEXT NOT NULL,
    round_number    INTEGER NOT NULL,
    patch_version   TEXT REFERENCES patches(version),
    state_json      JSONB NOT NULL,
    snapshot_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- tournaments: one per run, resumable
CREATE TABLE IF NOT EXISTS tournaments (
    id              TEXT PRIMARY KEY,
    config_json     JSONB NOT NULL,
    patch_version   TEXT REFERENCES patches(version),
    status          TEXT DEFAULT 'pending'
                    CHECK(status IN ('pending','running','completed','failed','abandoned')),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at      TIMESTAMP,
    ended_at        TIMESTAMP,
    winner_agent_id TEXT REFERENCES agents(id),
    seed            INTEGER,
    notes           TEXT
);

-- tournament_participants: which agents play which role in which tournament
CREATE TABLE IF NOT EXISTS tournament_participants (
    tournament_id    TEXT NOT NULL REFERENCES tournaments(id),
    agent_id         TEXT NOT NULL REFERENCES agents(id),
    role             TEXT NOT NULL CHECK(role IN ('debater_a','debater_b','judge')),
    starting_balance INTEGER DEFAULT 1000,
    final_balance    INTEGER,
    PRIMARY KEY (tournament_id, agent_id, role)
);

-- tournament_rounds: episodic traces — append-only, never update a row
CREATE TABLE IF NOT EXISTS tournament_rounds (
    id               BIGSERIAL PRIMARY KEY,
    idempotency_key  TEXT UNIQUE NOT NULL,
    tournament_id    TEXT NOT NULL REFERENCES tournaments(id),
    round_number     INTEGER NOT NULL,
    agent_id         TEXT REFERENCES agents(id),
    status           TEXT DEFAULT 'pending'
                     CHECK(status IN ('pending','running','completed','failed','cancelled','dead')),
    retry_count      INTEGER DEFAULT 0,
    transcript_json  JSONB,
    tokens_used      INTEGER,
    judge_scores     JSONB DEFAULT '{}',
    roi              REAL,
    patch_version    TEXT NOT NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at     TIMESTAMP,
    UNIQUE(tournament_id, round_number)   -- one row per round (single debate per round; agent_id triple removed as redundant)
);

-- indexes
CREATE INDEX IF NOT EXISTS idx_rounds_tournament
    ON tournament_rounds(tournament_id, round_number);
CREATE INDEX IF NOT EXISTS idx_rounds_agent
    ON tournament_rounds(agent_id, created_at);
CREATE INDEX IF NOT EXISTS idx_snapshots_agent_tournament
    ON agent_state_snapshots(agent_id, tournament_id, round_number);
CREATE INDEX IF NOT EXISTS idx_agents_patch
    ON agents(last_patch_applied);
CREATE INDEX IF NOT EXISTS idx_rounds_created_brin
    ON tournament_rounds USING BRIN(created_at);
```

**Also create:** `src/db/schema_sqlite.sql` — exact same schema but with these substitutions:
- `BIGSERIAL` → `INTEGER`
- `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` → `TEXT DEFAULT (datetime('now'))` (CURRENT_TIMESTAMP works in SQLite too but TEXT is safer)
- `JSONB` → `TEXT`
- `TEXT[]` → `TEXT`
- Remove `USING BRIN` from last index
- Remove `CHECK(state_json IS NULL OR json_typeof(state_json::json) = 'object')` — replace with `CHECK(state_json IS NULL OR json_valid(state_json))`

**Must NOT:** use ORM, add tables not listed, mix Postgres/SQLite syntax in same file

**Verify:**
```bash
python -c "
import sqlite3, sys
sql = open('src/db/schema_sqlite.sql').read()
conn = sqlite3.connect(':memory:')
try:
    conn.executescript(sql)
    tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
    expected = ['provider_configs','patches','agents','agent_state_snapshots','tournaments','tournament_participants','tournament_rounds']
    missing = [t for t in expected if t not in tables]
    print('PASS' if not missing else f'FAIL missing={missing}')
except Exception as e:
    print(f'FAIL {e}'); sys.exit(1)
"
```

---

## TASK-002 [status: blocked — needs TASK-001] [batch: B]
**Title:** DB connection module

**File:** `src/db/connection.py`

**Spec:**
```python
# Returns a connection based on DB_URL env var.
# DB_URL=sqlite:///data/league.db  (default, local dev)
# DB_URL=postgresql://user:pass@host/dbname  (production)
# Creates data/ dir and runs schema if SQLite.
# For Postgres: assumes schema already applied via migration.

import os, sqlite3
from pathlib import Path

DB_URL = os.getenv("DB_URL", "sqlite:///data/league.db")

def get_db():
    if DB_URL.startswith("sqlite"):
        path = DB_URL.split("///")[1]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        schema = Path(__file__).parent / "schema_sqlite.sql"
        conn.executescript(schema.read_text())
        return conn
    else:
        import psycopg2, psycopg2.extras
        conn = psycopg2.connect(DB_URL)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn
```

**Verify:**
```bash
python -c "
from src.db.connection import get_db
db = get_db()
tables = [r[0] for r in db.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
assert 'agents' in tables and 'tournament_rounds' in tables
print('PASS')
"
```

---

## TASK-003 [status: blocked — needs TASK-001] [batch: B]
**Title:** Core CRUD ops layer

**File:** `src/db/ops.py`

**Spec:** Functions only, no classes. All take `conn` as first arg.

```python
# agents
def upsert_agent(conn, id, name, provider_config_id, **kwargs) -> None
def get_agent(conn, id) -> dict | None
def update_agent_state(conn, id, **fields) -> None   # updates any column in agents

# tournaments
def create_tournament(conn, id, config_json, patch_version, seed) -> None
def update_tournament_status(conn, id, status, **kwargs) -> None
def get_tournament(conn, id) -> dict | None

# rounds
def insert_round(conn, idempotency_key, tournament_id, round_number, agent_id, patch_version) -> None
def update_round(conn, idempotency_key, status, **kwargs) -> None
def get_last_completed_round(conn, tournament_id) -> dict | None   # for resume

# participants
def add_participant(conn, tournament_id, agent_id, role, starting_balance) -> None
def set_participant_final_balance(conn, tournament_id, agent_id, final_balance) -> None

# snapshots
def save_snapshot(conn, agent_id, tournament_id, round_number, patch_version, state_json) -> None
```

**Must NOT:** commit inside these functions — caller controls transactions.

**Verify:**
```bash
python -c "
from src.db.connection import get_db
from src.db import ops
conn = get_db()
ops.upsert_agent(conn, 'test_agent', 'Test', None)
a = ops.get_agent(conn, 'test_agent')
assert a['name'] == 'Test', f'got {a}'
ops.create_tournament(conn, 'test_t1', '{}', None, 42)
ops.update_tournament_status(conn, 'test_t1', 'running')
t = ops.get_tournament(conn, 'test_t1')
assert t['status'] == 'running'
conn.commit()
print('PASS')
"
```

---

## TASK-004A [status: blocked — needs TASK-001] [batch: B]
**Title:** Rename openai_compat_backend → provider_backend (rename only, no deletes)

**Files:**
- RENAME: `src/models/openai_compat_backend.py` → `src/models/provider_backend.py`

**Spec:**
- Copy file, update class names inside:
  - `OpenAICompatBackend` → `ProviderBackend`
  - `OpenAICompatConfig` → `ProviderConfig`
- Do NOT yet update debater.py or judge.py (that's 004B)
- Do NOT delete any files

**Why split from 004B:** Rename is low-risk and git-reversible. Delete + multi-file edits are high-risk.
If 004B breaks tests, 004A can stay while 004B rolls back.

**Verify:**
```bash
python -c "from src.models.provider_backend import ProviderBackend, ProviderConfig; print('PASS import')"
```

---

## TASK-004B [status: blocked — needs TASK-004A] [batch: B]
**Title:** Delete legacy backends, wire debater/judge to ProviderBackend

**Files:**
- DELETE: `src/models/ollama_backend.py`
- DELETE: `src/models/vllm_backend.py`
- DELETE: `src/models/openai_compat_backend.py`  (original, kept after rename; now remove)
- EDIT: `src/models/debater.py`
- EDIT: `src/models/judge.py`
- EDIT: `src/models/__init__.py`

**BLOCKER ALREADY FIXED (do not re-do):**
`provider_backend.py` previously imported `GenerationResult` from `ollama_backend`.
That import has been removed and `GenerationResult` is now defined directly in `provider_backend.py`.

**Remaining spec:**

In `debater.py`:
- Remove the conditional `from .ollama_backend import get_backend, OllamaConfig` block (~line 142)
- Change `from .ollama_backend import GenerationResult` (~line 206) →
  `from .provider_backend import GenerationResult, ProviderBackend, ProviderConfig`
- Remove all `vllm` backend branches
- Any non-stub backend dispatch → `ProviderBackend(ProviderConfig(...))`
- Keep `stub:` branch untouched

In `judge.py`:
- Same pattern: remove `ollama` and `vllm` branches
- Change `from .ollama_backend import GenerationResult` (~line 172) →
  `from .provider_backend import GenerationResult, ProviderBackend, ProviderConfig`
- Keep `stub:` branch untouched

In `src/models/__init__.py` — replace entire file with:
```python
from .debater import Debater, DebaterConfig, Argument, BetType, BetDecision
from .judge import BaseJudge, LLMJudge, EnsembleJudge, ConsensusJudge, Judge, JudgeConfig, Judgment
from .provider_backend import ProviderBackend, ProviderConfig, GenerationResult
from .response_models import JudgmentResponse, DeliberationResponse

__all__ = [
    "Debater", "DebaterConfig", "Argument", "BetType", "BetDecision",
    "BaseJudge", "LLMJudge", "EnsembleJudge", "ConsensusJudge", "Judge", "JudgeConfig", "Judgment",
    "ProviderBackend", "ProviderConfig", "GenerationResult",
    "JudgmentResponse", "DeliberationResponse",
]
```

Delete with `git rm`:
- `src/models/ollama_backend.py`
- `src/models/vllm_backend.py`
- `src/models/openai_compat_backend.py`

**Verify:**
```bash
python -c "from src.models.provider_backend import ProviderBackend, ProviderConfig, GenerationResult; print('PASS import')"
python -c "from src.models import GenerationResult; print('PASS __init__ re-export')"
python -m pytest tests/ -x -q 2>&1 | tail -5
```

---

## TASK-005 [status: blocked — needs TASK-001] [batch: B]
**Title:** Patch registration script

**File:** `scripts/register_patch.py`

**Spec:** CLI tool. Usage:
```
python scripts/register_patch.py \
  --version "v1.3-20260306" \
  --description "Economy pot raised 40->200. Arguing now EV-positive." \
  --affected "economy.pot,economy.break_even" \
  --delta '{"pot": 200, "old_pot": 40}'
```
- Inserts row into `patches` table
- Prints `[patch] registered v1.3-20260306`
- If version already exists: print `[patch] already exists, skipping`
- On startup, auto-registers the 3 patches already applied this project:
  - `v1.0-20260304`: "Initial economy. Pot=40, self-judge."
  - `v1.1-20260306`: "Economy fix: pot 40->200. External judge llama-3.3-70b."
  - `v1.2-20260306`: "Deliberation prompt v2: cost ratio visible, delib cost disclosed."

**Verify:**
```bash
python scripts/register_patch.py --version "v_test" --description "test patch" --affected "test" --delta '{}'
python -c "
from src.db.connection import get_db
p = get_db().execute(\"SELECT * FROM patches WHERE version='v_test'\").fetchone()
assert p is not None
print('PASS')
"
```

---

## TASK-006 [status: blocked — needs TASK-001] [batch: B]
**Title:** Agent registry module

**File:** `src/db/agent_registry.py`

**Spec:**
```python
def register_agent(conn, model_id: str, provider_base_url: str, api_key: str = None) -> str:
    # Creates or returns existing agent id
    # id = slugify(f"{model_id}_{urlparse(provider_base_url).netloc}")
    # Upserts provider_config row, then upserts agent row
    # Returns agent id

def get_or_create_agent(conn, model_id: str, provider_base_url: str, api_key: str = None) -> dict:
    # Calls register_agent, returns full agent row

def apply_patch_notification(conn, agent_id: str, current_patch: str) -> str | None:
    # If agent.last_patch_applied != current_patch:
    #   return delta summary string for injection into system prompt
    #   e.g. "PATCH NOTES since your last run (v1.1 -> v1.2): Deliberation prompt updated..."
    # Else return None (agent is current)
```

**Verify:**
```bash
python -c "
from src.db.connection import get_db
from src.db.agent_registry import register_agent, apply_patch_notification
conn = get_db()
aid = register_agent(conn, 'qwen/qwen3-32b', 'https://api.groq.com/openai/v1')
assert aid is not None and len(aid) > 3
conn.commit()
print('PASS', aid)
"
```

---

## TASK-007 [status: blocked — needs BATCH B] [batch: C]
**Title:** Provider health check

**File:** `src/db/health_check.py`

**Spec:** `check_provider(config: ProviderConfig, conn=None) -> bool`
- GET `{base_url}/v1/models` with auth header, 5s timeout
- Returns True if 200 + at least one model in response
- If conn provided: updates `provider_configs.last_health_ok`
- Prints `[health] OK {model_id}` or `[health] FAIL {reason}`

**Verify:**
```bash
python -c "
from src.db.health_check import check_provider
from src.models.provider_backend import ProviderConfig
result = check_provider(ProviderConfig(base_url='http://localhost:1', model='x'))
assert result == False
print('PASS — dead endpoint returns False cleanly')
"
```

---

## TASK-008 [status: blocked — needs BATCH B] [batch: C]
**Title:** Tournament round DB writer

**File:** `src/db/round_writer.py`

**Spec:** Drop-in replacement for the current JSON file writing in `src/arena/dynamic_round.py`.

```python
class RoundWriter:
    def __init__(self, conn, tournament_id: str, patch_version: str)
    def begin_round(self, round_number: int, agent_id: str) -> str:
        # inserts pending round row, returns idempotency_key (UUID)
    def complete_round(self, idempotency_key: str, transcript: dict,
                       tokens_used: int, judge_scores: dict, roi: float) -> None:
        # updates round to completed, sets completed_at
    def fail_round(self, idempotency_key: str, reason: str) -> None:
        # increments retry_count
        # if retry_count < 3: status='failed' (eligible for retry)
        # if retry_count >= 3: status='dead' (give up)
        # stores reason in judge_scores column as {"error": reason}
        # never raises — fail_round must be safe to call in an except block
```

**Verify:**
```bash
python -c "
from src.db.connection import get_db
from src.db.ops import upsert_agent, create_tournament
from src.db.round_writer import RoundWriter
import uuid
conn = get_db()
upsert_agent(conn, 'a1', 'TestAgent', None)
create_tournament(conn, 't1', '{}', None, 1)
conn.commit()
rw = RoundWriter(conn, 't1', 'v1.0')
key = rw.begin_round(1, 'a1')
rw.complete_round(key, {'text': 'hello'}, 100, {'accuracy': 0.7}, 0.05)
conn.commit()
row = conn.execute(\"SELECT status FROM tournament_rounds WHERE idempotency_key=?\", (key,)).fetchone()
assert row['status'] == 'completed'
print('PASS')
"
```

---

## TASK-009 [status: blocked — needs BATCH B] [batch: C]
**Title:** Tournament resume loader

**File:** `src/db/resume.py`

**Spec:**
```python
def get_resumable_tournament(conn, tournament_id: str) -> dict | None:
    # Returns tournament row if status in ('running','failed')
    # Returns None if completed/abandoned/not found

def get_resume_point(conn, tournament_id: str) -> int:
    # Returns next round_number to run
    # = last completed round_number + 1, or 1 if none

def mark_stale_rounds_dead(conn, tournament_id: str, timeout_minutes: int = 5) -> int:
    # Any round with status='running' and created_at older than timeout -> status='dead'
    # Returns count of rounds marked dead
```

**Verify:**
```bash
python -c "
from src.db.connection import get_db
from src.db.ops import create_tournament, insert_round, update_round
from src.db.resume import get_resume_point, mark_stale_rounds_dead
import uuid
conn = get_db()
create_tournament(conn, 'rt1', '{}', None, 99)
insert_round(conn, str(uuid.uuid4()), 'rt1', 1, None, 'v1.0')
key2 = str(uuid.uuid4())
insert_round(conn, key2, 'rt1', 2, None, 'v1.0')
update_round(conn, key2, 'completed')
conn.commit()
pt = get_resume_point(conn, 'rt1')
assert pt == 3, f'expected 3 got {pt}'
print('PASS resume_point=3')
"
```

---

## TASK-010 [status: blocked — needs BATCH B] [batch: C]
**Title:** Leaderboard queries

**File:** `src/db/leaderboard.py`

**Spec:**
```python
def get_leaderboard(conn, limit: int = 20) -> list[dict]:
    # Returns agents sorted by career_roi DESC
    # Fields: id, name, career_wins, career_losses, career_roi, last_active_at

def get_agent_history(conn, agent_id: str, limit: int = 50) -> list[dict]:
    # Returns last N completed rounds for agent
    # Fields: tournament_id, round_number, roi, judge_scores, patch_version, completed_at

def get_patch_impact(conn, patch_version: str) -> dict:
    # Returns avg roi before vs after patch for all agents
    # {before_avg_roi, after_avg_roi, agent_count, round_count}
```

**Verify:**
```bash
python -c "
from src.db.connection import get_db
from src.db.leaderboard import get_leaderboard, get_patch_impact
conn = get_db()
lb = get_leaderboard(conn)
assert isinstance(lb, list)
pi = get_patch_impact(conn, 'nonexistent_patch')
assert isinstance(pi, dict)
print('PASS')
"
```

---

## TASK-011 [status: blocked — needs BATCH C] [batch: D]
**Title:** Config → provider_config bridge

**File:** `src/db/config_bridge.py`

**Spec:** `register_from_yaml(conn, config_path: str) -> list[str]`
- Reads existing YAML tournament config
- For each debater + judge model: calls `agent_registry.register_agent`
- Returns list of agent ids registered
- Handles both old format (`model: "openai:qwen/qwen3-32b"`) and new format (`model: "qwen/qwen3-32b"`)
- Base URL from `OPENAI_COMPAT_BASE_URL` env var

**Verify:**
```bash
python -c "
import os; os.environ['OPENAI_COMPAT_BASE_URL'] = 'https://api.groq.com/openai/v1'
from src.db.connection import get_db
from src.db.config_bridge import register_from_yaml
conn = get_db()
ids = register_from_yaml(conn, 'configs/clean_economy_groq.yaml')
assert len(ids) >= 2
conn.commit()
print('PASS registered:', ids)
"
```

---

## TASK-012 [status: blocked — needs BATCH C] [batch: D]
**Title:** Migrate existing clean_100 JSON logs into DB

**File:** `scripts/migrate_json_logs.py`

**Spec:** CLI: `python scripts/migrate_json_logs.py --batch-dir logs/clean_overnight_01/clean_100`
- Reads `batch_summary.jsonl`
- For each successful run: creates tournament row, participant rows, round rows from transcript
- Skips already-imported tournaments (idempotent on tournament id)
- Assigns patch_version `v1.1-20260306` to all clean_100 runs
- Prints progress: `[migrate] run 001/099 tournament_id=xxx`
- Final: `[migrate] done: 99 imported, 0 skipped, 0 failed`

**Must NOT:** import contaminated log directories (groq_multikey, overnight, evolution, nvidia_afternoon)

**Verify:**
```bash
python scripts/migrate_json_logs.py --batch-dir logs/clean_overnight_01/clean_100
python -c "
from src.db.connection import get_db
conn = get_db()
count = conn.execute('SELECT COUNT(*) FROM tournaments').fetchone()[0]
assert count >= 90, f'expected ~99 got {count}'
print(f'PASS: {count} tournaments in DB')
"
```

---

## TASK-013 [status: blocked — needs TASK-008 + TASK-009] [batch: D]
**Title:** Wire arena to DB writer (additive, backward-compatible)

**File:** `src/arena/dynamic_round.py`

**Context:**
`DynamicDebateRound` is the core arena class (~852 lines). It has `__init__` and `run()`.
Currently it writes results to JSON files only (via `RoundTranscript`). This task adds
an optional DB write path alongside the existing JSON path — no JSON removed.

**Spec:** Add one optional parameter to `DynamicDebateRound.__init__`:
```python
round_writer: Optional["RoundWriter"] = None  # from src.db.round_writer
```

In `run()` (line ~170), wrap execution:
```python
idempotency_key = None
if self.round_writer:
    idempotency_key = self.round_writer.begin_round(round_id, agent_id=None)
try:
    result = <existing execution logic>
    if self.round_writer and idempotency_key:
        judge_scores = {
            "confidence_a": result.final_judgment.confidence_a,
            "confidence_b": result.final_judgment.confidence_b,
        }
        tokens_used = int(result.gen_cost_a + result.gen_cost_b)
        roi = float(result.tokens_awarded_a + result.tokens_awarded_b)
        self.round_writer.complete_round(idempotency_key, {}, tokens_used, judge_scores, roi)
    return result
except Exception as exc:
    if self.round_writer and idempotency_key:
        self.round_writer.fail_round(idempotency_key, str(exc))
    raise
```

**Must NOT:** remove any existing JSON writing logic. This is additive only.
**Must NOT:** import from src.db at module level — use TYPE_CHECKING guard to avoid circular import:
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..db.round_writer import RoundWriter
```

**Verify:**
```bash
python -c "
import inspect
from src.arena.dynamic_round import DynamicDebateRound
sig = inspect.signature(DynamicDebateRound.__init__)
assert 'round_writer' in sig.parameters, 'round_writer param missing'
print('PASS — round_writer parameter present')
"
```

---

## TASK-014 [status: blocked — needs TASK-013 + TASK-011] [batch: D]
**Title:** League entry point — start or resume a tournament with DB persistence

**File:** `run_league.py` (repo root)

**Spec:** CLI entry point that runs a full tournament with DB persistence and resume support.

```
python run_league.py --config configs/clean_economy_groq.yaml [--tournament-id <id>] [--seed <n>]
```

- If `--tournament-id` given and tournament exists in DB with status running/failed:
  - Resume from `get_resume_point()` — skip already-completed rounds
  - Print `[league] resuming tournament {id} from round {n}`
- Else: create new tournament in DB, register agents via `config_bridge.register_from_yaml`
  - Print `[league] starting new tournament {id}`
- For each round: use `DynamicDebateRound` with a `RoundWriter` attached
- Apply patch notifications to agents via `apply_patch_notification` before each run
  (inject result into debater system_prompt prefix if not None)
- On completion: set tournament status=completed, update agent career stats
  (career_wins += 1 for winner, career_losses += 1 for loser, career_roi updated)
- Print leaderboard at end via `get_leaderboard(conn, limit=10)`
- Handles Ctrl+C gracefully: sets tournament status=failed (resumable), prints `[league] paused`

**Current patch version to use:** `"v1.2-20260306"` (latest registered patch)

**Must NOT:** break existing `demo_tournament.py` — run_league.py is a new file

**Verify:**
```bash
python -c "
import sys
from pathlib import Path
assert Path('run_league.py').exists(), 'run_league.py missing'
import ast
tree = ast.parse(Path('run_league.py').read_text())
fns = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
print('PASS — functions:', fns)
"
```
