# AICampTownDebate

Adversarial token-economy debate for inference-time compute experiments.

## What It Does

- Runs two debaters against each other across one or many rounds.
- Uses a token ledger where generation, deliberation, search, and summarization consume balance.
- Uses modular judges (`single`, `ensemble`, `consensus`) with multi-dimension scoring.
- Supports dynamic rounds that continue until mutual `PASS` or max iterations.

## Current Decision Model

Debater deliberation outputs:
- `RESPOND`: place a bet and generate a counter response (optionally `use_search: true`)
- `PASS`: stop acting this iteration

## Backends

Model strings can be provided as:
- `ollama:<model>`
- `vllm:<model>`
- `stub`

If no prefix is provided, demos default to `ollama:`.

## Setup

```bash
pip install -r requirements.txt
```

If you use Ollama:

```bash
ollama serve
ollama pull qwen2.5:1.5b
```

If you use search during debate, `ddgs` is already included in `requirements.txt`.

## Run

Dynamic single-round demo:

```bash
python demo_dynamic.py --config configs/tournament_config.yaml
```

Tournament demo:

```bash
python demo_tournament.py --config configs/tournament_config.yaml
```

## Project Status

Core mechanics are implemented and testable, but this is still an experimental framework and defaults may evolve.

## Documentation

- `CONCEPT.md`: theory and goals
- `DEVLOG.md`: recent implementation log
- `docs/architecture.md`: architecture and module map
- `docs/PROCEDURES.md`: reproducible run procedure
- `docs/ECONOMIC_ANALYSIS.md`: economic assumptions and math notes
