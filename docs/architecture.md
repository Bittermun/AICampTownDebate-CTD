# System Architecture

## Overview

AICampTownDebate runs a two-debater tournament loop with a shared token economy. The core flow:

1. Debaters generate initial arguments (costs deducted).
2. Judge evaluates both arguments (multi-dimension scoring).
3. Optional initial bounty split (`split_pot_enabled`).
4. Iterative betting loop:
   - Debaters deliberate with `<thinking>` and choose `RESPOND` or `PASS`
   - `RESPOND`: place bet (stake + scaling fee), optional search, generate counter under `max_budget` cap
   - Judge re-evaluates with comparative context (sees prior judgment)
5. Loop ends on mutual `PASS`, bankruptcy, or `max_iterations`.
6. Pot and bet resolutions applied to ledger. Accounting audit run.
7. Transcripts saved (JSON + Markdown).

## Active Components

### Entry Points
- `demo_dynamic.py` — single-round dynamic debate
- `demo_tournament.py` — multi-round tournament with optional judge gates

### Config
- `src/config_loader.py` — YAML loader producing `TournamentConfig` dataclass
- Key fields: `DebaterSpec` (model, EV guard, Kelly, multi-agent), `JudgeSpec`, `EconomyConfig`, `RoundConfig`
- BOM-safe (`utf-8-sig` encoding)

### Debaters
- `src/models/debater.py` (~914 lines)
- Backend dispatch: `stub`, `ollama`, `vllm`, `openai_compat`, `llama_cpp`
- `generate_argument()` — main generation with `<thinking>` extraction
- `decide_bet()` — deliberation with Pydantic parsing, Kelly sizing, EV guard
- `summarize_position()` — LLM-generated memory compression
- `_build_peer_draft()` — multi-agent critique/synthesize injection (experimental)
- Note: `HOLD` in JSON maps to `BetType.PASS`

### Judges
- `src/models/judge.py` (~814 lines)
- `LLMJudge` — primary. Uses `AllocationJudgment` (integer splits), falls back to `MultiDimensionJudgment` (floats), then regex rescue
- `EnsembleJudge` — two evaluations with swapped order, averaged
- `ConsensusJudge` — sub-judges + lead instructor synthesis
- Confidence clamped to 5-95%
- Optional `randomize_argument_order` per evaluation call
- Prompts in `src/models/judge_prompts.py`

### Economy
- `src/economy/ledger.py` — `TokenLedger` with register/award/deduct/transfer. All transactions logged.
- `src/economy/betting.py` — `BettingManager`. Deducts stake + fee, resolves bets with multiplier. Supports `custom_fee_rate` for iteration scaling.
- `src/economy/distribution.py` — `TokenDistributor`. Pari-mutuel pot split by final confidence ratio. Leak detection via assert.
- `src/economy/calibration.py` — derives economy params from survival targets.

### Round Engine
- `src/arena/dynamic_round.py` (~852 lines)
- `DynamicRoundContext` tracks all state
- Four phases: generate, judge, bet-loop, distribute
- Async parallel generation when both backends support it
- `_audit_round_accounting()` — checks minted - burned == supply delta (0.01 tolerance)
- Passes `prior_judgment` to judge each iteration (comparative memory)

### Tournament
- `src/arena/tournament.py`
- Multi-round loop over topic list
- Early stopping: bankruptcy (balance <= 0) or SPRT unrecoverable delta
- Records round outcomes into debater `StrategyMemory`
- **Bug:** `save_results()` winner field — `self._eliminated is False` never matches (value is `None` or string). Works by accident via fallthrough.

### Observers
- `src/arena/observers.py`
- `MetricsObserver` — efficiency, aggression, pass rate, momentum, elapsed time
- `HealthCheckObserver` — flags ALL_PASS, HIGH_VALIDATION_FAILURE, ZERO_BETS

### Analysis
- `src/analysis/judge_calibration.py` — pre-tournament calibration gate (3 fixed test cases)
- `src/analysis/judge_variance.py` — repeated evaluation stdev measurement
- `src/analysis/selection_health.py` — post-tournament dashboard (pass rate, entropy, adaptation gain)
- `src/analysis/trace_contract.py` — normalizes transcript turns into structured `TraceRecord`s
- `src/analysis/trajectory_parser.py` — extracts per-debater iteration data from markdown transcripts. **Fragile: uses emoji-based turn splitting.**

### Benchmark
- `src/benchmark/runner.py` — phase-1 benchmark orchestrator with gates, provenance, claim posture (L0/L1/L2)
- `src/benchmark/types.py` — result dataclasses
- `src/benchmark/batch_utils.py` — atomic writes, JSONL, checkpointing
- `src/benchmark/submission_packet.py` — validates and packages artifacts
- `src/benchmark/scoring.py`, `config_models.py`, `datasets.py`, `registry.py`

### Training Data
- `src/training/contracts.py` — `build_sft_examples_from_traces()`, `build_preference_pairs_from_rounds()`
- `src/training/data_prep.py` — orchestrator reading benchmark artifacts
- `src/training/trainer_interface.py` — **STUB.** `TrainerInterface` Protocol with no implementation.
- `src/training/checkpoint_registry.py` — checkpoint tracking (no real trainer backend)

### Evolution
- `src/evolution/campaign.py` — `EvolutionCampaign` with `DIRECTIVE_LIBRARY` of named strategies. Mutates `StrategyProfile` genomes, evaluates via `run_phase1()`, selects elites.

### Memory
- `src/memory/strategy_memory.py` — `StrategyMemory` with `record_outcome()` and `render_playbook()`. Keyword-heuristic strategy classification.

### Other
- `src/prompting/rule_cards.py` — loads/renders prompt rule cards from `configs/rule_cards/`
- `src/runtime/preflight.py` — backend readiness checks, `--allow-stub` fallback
- `src/tools/research.py` — DuckDuckGo search with token cost
- `src/integrations/match_registry.py` — SQLite/Postgres cross-session match storage
- `src/logs/transcript.py` — `Turn`, `RoundTranscript`, `DebateTranscript` with JSON/Markdown export
- `src/models/response_models.py` — Pydantic models for judgments and deliberation
- `src/models/ollama_backend.py`, `vllm_backend.py`, `openai_compat_backend.py` — all fully functional

## Dead Code

| File | Why it's dead |
|------|---------------|
| `src/arena/round.py` | Old single-pass `DebateRound`. Not imported by any demo, tournament, or test. Fully superseded by `DynamicDebateRound`. |
| `src/models/judge_factory.py` | `JudgeFactory` with static methods. Never imported — demos build judges inline. |
| `src/models/protocols.py` | `LLMBackend`, `JudgeProtocol`, `DebaterProtocol` Protocol definitions. Not imported by production code. Serves only as documentation of intent. |
| `Debater.generate_research()` | Method in `debater.py`. Unreachable — the research path in `dynamic_round.py` goes through `generate_argument()` with `research_context` param instead. |

## Broken / Aspirational

| File | Issue |
|------|-------|
| `src/economy/bank.py` (untracked) | Imports `from ..models.base_model import BaseBackend` — file does not exist. `_build_evaluation_prompt()` returns `"{}"`, `_parse_loan_plans()` returns `[]`. Not wired into any code path. |
| `src/training/trainer_interface.py` | Empty Protocol. No implementation anywhere. |

## Repository Map

```
src/
  config_loader.py          Config YAML -> TournamentConfig
  models/
    debater.py              Core debater (generation, deliberation, memory)
    judge.py                LLM/Ensemble/Consensus judges
    judge_prompts.py        Judge prompt templates
    response_models.py      Pydantic schemas
    ollama_backend.py       Ollama HTTP backend
    vllm_backend.py         vLLM OpenAI-compat backend
    openai_compat_backend.py  Generic OpenAI-compat backend
    protocols.py            [DEAD] Protocol definitions
    judge_factory.py        [DEAD] Unused factory
  economy/
    ledger.py               Token ledger + transactions
    betting.py              Bet placement + resolution
    distribution.py         Pot distribution
    calibration.py          Economy param derivation
    bank.py                 [BROKEN/UNTRACKED] Aspirational bank agent
  arena/
    dynamic_round.py        Core round engine
    tournament.py           Multi-round tournament runner
    round.py                [DEAD] Old single-pass round
    observers.py            Metrics + health check observers
  benchmark/                Phase-1 benchmark suite
  training/                 Training data export (no training loop)
  evolution/                Evolutionary campaign system
  memory/                   Cross-round strategy memory
  analysis/                 Judge calibration, variance, selection health, traces
  prompting/                Rule card loading
  runtime/                  Preflight checks
  tools/                    DuckDuckGo search
  integrations/             SQLite/Postgres match registry
  logs/                     Transcript generation

configs/                    YAML tournament/benchmark presets
tests/                      Mix of pytest tests and standalone runner scripts
scripts/                    Batch runners, PowerShell pipelines
```
