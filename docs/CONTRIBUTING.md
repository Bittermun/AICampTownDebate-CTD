# Contributing to AICampTownDebate

## Focus Areas

### 1. Model Backends
- Backend wrappers live in `src/models/`.
- If adding a backend, support sync generation and token usage tracking.

### 2. Judge Quality
- Judge logic and prompts:
  - `src/models/judge.py`
  - `src/models/judge_prompts.py`
  - `src/models/response_models.py`
- Keep scoring schemas strict and resilient to malformed model output.

### 3. Economy + Round Logic
- Economy:
  - `src/economy/ledger.py`
  - `src/economy/betting.py`
  - `src/economy/distribution.py`
- Round orchestration:
  - `src/arena/dynamic_round.py`
  - `src/arena/tournament.py`

### 4. Logging + Analysis
- Transcript and export:
  - `src/logs/transcript.py`
- Trajectory parsing:
  - `src/analysis/trajectory_parser.py`

## Development Setup

```bash
pip install -r requirements.txt
```

Optional runtime services:
- Ollama for `ollama:` models
- vLLM for `vllm:` models

## Validation

Run verification suite:

```bash
python tests/test_suite.py
```

Run demos:

```bash
python demo_dynamic.py --config configs/tournament_config.yaml
python demo_tournament.py --config configs/tournament_config.yaml
```

## Standards

- Use type hints.
- Keep parsing/validation explicit at LLM boundaries.
- Prefer tests for behavior changes in judge/economy/round logic.
- Document meaningful architectural changes in `DEVLOG.md`.
