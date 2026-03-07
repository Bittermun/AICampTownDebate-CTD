-- # TASK-001 output - see CODEX_QUEUE.md
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
-- NOTE: snapshots are manual/optional - taken on patch apply or tournament end only.
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

-- tournament_rounds: episodic traces - append-only, never update a row
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
    UNIQUE(tournament_id, round_number, agent_id),
    UNIQUE(tournament_id, round_number)   -- one row per round (single debate per round)
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
