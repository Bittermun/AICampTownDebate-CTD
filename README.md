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

If using Ollama:

```bash
ollama serve
ollama pull qwen2.5:1.5b
```

## Run

Strict dynamic run (recommended):

```bash
python demo_dynamic.py --config configs/tournament_config.yaml
```

Strict tournament run (recommended):

```bash
python demo_tournament.py --config configs/tournament_config.yaml --gate-judge-variance
```

Recommended Ollama scale-up run (available on this machine now):

```bash
python demo_tournament.py --config configs/ollama_tournament_recommended.yaml --gate-judge-variance
```

Recommended vLLM research tournament (24 rounds):

```bash
set VLLM_BASE_URL=http://localhost:8000
python demo_tournament.py --config configs/vllm_tournament_recommended.yaml --gate-judge-variance
```

Helper scripts:

```bash
powershell -ExecutionPolicy Bypass -File scripts/run_research_tournament.ps1
powershell -ExecutionPolicy Bypass -File scripts/start_vllm_docker.ps1
powershell -ExecutionPolicy Bypass -File scripts/run_vllm_research.ps1
```

The one-command vLLM runner emits:
- `logs/vllm_research_summary_<timestamp>.json` (winner, balance spread, mean pass/aggression, judge variance, artifact paths)
- `logs/selection_health_dashboard_<timestamp>.json` (selection health metrics: pass/aggression, entropy, adaptation, health score)

Development fallback run (allows stub/fallback, not valid for serious data):

```bash
python demo_tournament.py --config configs/tournament_config.yaml --allow-stub
```

## Experiment Utilities

Judge variance stress test:

```bash
python tests/stress_judge_variance.py --model ollama:qwen2.5:1.5b
```

Baseline vs economy comparison:

```bash
python tests/reproduce_baseline_vs_economy.py --config configs/tournament_config.yaml
```

Economy calibration from runway assumptions:

```bash
python tests/derive_economy_params.py --survival-rounds 6 --avg-generation-cost 30 --avg-bet-size 20
```

## Documentation

- `CONCEPT.md`: theory and goals
- `DEVLOG.md`: recent implementation log
- `docs/architecture.md`: architecture and module map
- `docs/PROCEDURES.md`: reproducible run procedure
- `docs/ECONOMIC_ANALYSIS.md`: economic assumptions and math notes
