# Procedures

## Environment

- Windows/Linux/macOS with Python 3.11+
- Optional backend service(s):
  - Ollama server for `ollama:` models
  - vLLM server for `vllm:` models
- Python deps from `requirements.txt`

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. If using Ollama, start service and pull a model:

```bash
ollama serve
ollama pull qwen2.5:1.5b
```

3. Configure `configs/tournament_config.yaml`.

## Dynamic Debate Run

```bash
python demo_dynamic.py --config configs/tournament_config.yaml
```

Round flow:
1. Opening arguments are generated.
2. Judge scores both sides (multi-dimension scoring).
3. Each debater deliberates with private `<thinking>` and chooses `RESPOND` or `PASS`.
4. On `RESPOND`, debater places a bet and generates a counter response; `use_search=true` can call DDGS search.
5. Iteration fee scales with iteration (`5% * iteration`, capped at `50%`).
6. Repeat until mutual `PASS` or `max_iterations`.
7. Final distribution and bet resolution are recorded.

## Tournament Run

```bash
python demo_tournament.py --config configs/tournament_config.yaml
```

- Runs `num_rounds` over configured topic list.
- Uses `rounds.max_iterations` per round.
- Persists ledger and transcript artifacts to `logs/`.

## Output Artifacts

- Transcript JSON and Markdown
- Round/tournament summaries
- Ledger JSON with timestamped transactions
- Optional observer metrics

## Current Defaults (from `configs/tournament_config.yaml`)

- `initial_balance`: 350
- `max_debt`: 50
- `tokens_per_round`: 120
- `num_rounds`: 10
- `max_iterations`: 5
