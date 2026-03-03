# System Architecture

## Overview

AICampTownDebate currently centers on a two-debater tournament loop with a shared token economy:

1. Debaters generate initial arguments.
2. Judge evaluates both arguments.
3. Debaters deliberate and choose `RESPOND` or `PASS`.
4. `RESPOND` can optionally call web search (`use_search: true`) and then generate a new counter response.
5. Judge re-evaluates.
6. Loop ends on mutual `PASS`, bankruptcy, or `max_iterations`.
7. Pot and bet resolutions are applied to ledger, then logs/transcripts are saved.

## Major Components

### Debaters
- File: `src/models/debater.py`
- Supports `ollama:`, `vllm:`, `openai:`, `stub`, and llama.cpp path modes.
- Tracks generation token usage and exposes deliberation with budget control (`max_budget`).
- Loads compact prompt rule cards from `configs/rule_cards/` when present.

### Judges
- File: `src/models/judge.py`
- `LLMJudge`, `EnsembleJudge`, `ConsensusJudge`.
- Uses multi-dimension judging model (accuracy/responsiveness/development).
- Optional argument-order randomization to reduce positional bias.

### Economy
- Files: `src/economy/ledger.py`, `src/economy/betting.py`, `src/economy/distribution.py`
- Ledger records balances and timestamped transactions.
- Bets include stake and fee burn.
- Iteration fee scaling is applied in dynamic round flow.

### Round Engine
- File: `src/arena/dynamic_round.py`
- Dynamic iterative control loop.
- Handles deliberation costs, search costs, summarization costs, and final distribution.

### Tournament Runner
- File: `src/arena/tournament.py`
- Runs multiple rounds over topic list.
- Uses config-driven `num_rounds` and `max_iterations`.

### Logging
- File: `src/logs/transcript.py`
- Saves JSON + Markdown transcripts with arguments, deliberations, judgments, payouts.

### Benchmark Orchestrator
- Files: `src/benchmark/*.py`
- Runs phase-1 benchmark policy across seeds.
- Tracks gate outcomes, score provenance (`fixture_static` vs `model_derived`), and artifact manifests.

### Prompting
- Files: `src/prompting/*.py`
- Rule-card loader/rendering for compact, versioned prompt controls.

### Integrations
- Files: `src/integrations/*.py`
- Match registry storage for cross-session tournament and leaderboard analysis (SQLite/Postgres).

## Repository Map

- `src/config_loader.py`: YAML config loader
- `src/models/`: debaters, judges, backends, response schemas
- `src/prompting/`: rule-card loading and prompt view rendering
- `src/economy/`: ledger, betting, distribution
- `src/arena/`: dynamic round, tournament, observers
- `src/benchmark/`: phase-1 benchmark policy execution and scoring
- `src/logs/`: transcript generation
- `src/integrations/`: cross-session persistence integrations
- `src/tools/research.py`: DDGS web search integration
- `tests/`: verification and stress scripts
- `configs/`: tournament config presets

## Config Notes

Primary config file is `configs/tournament_config.yaml`.

Key fields:
- `models.judge_type`: `single | ensemble | consensus`
- `models.randomize_argument_order`: `true | false`
- `models.debaters[].model`, `models.judges[].model`: supports prefixed model paths
- `economy`: balances/pot parameters
- `rounds.num_rounds`, `rounds.max_iterations`, `rounds.topics`

League/ranking and benchmark controls are defined in `configs/benchmark_phase1.yaml`.
