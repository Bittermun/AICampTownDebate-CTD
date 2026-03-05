# Procedures

## Environment

- Windows/Linux/macOS with Python 3.11+
- Optional backend service(s):
  - Ollama server for `ollama:` models
  - vLLM server for `vllm:` models
  - Any OpenAI-compatible endpoint for `openai:` models
- vLLM endpoint can be configured with `VLLM_BASE_URL` and optional `VLLM_API_KEY`
- OpenAI-compatible endpoint can be configured with `OPENAI_COMPAT_BASE_URL` and optional `OPENAI_COMPAT_API_KEY`
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
4. If using `openai:` models, set endpoint environment variables and use a matching config (for example `configs/openai_compat_tournament_recommended.yaml`).

## Safety Modes

- Default demos run in strict preflight mode.
- Strict mode blocks runs when backend/model checks fail.
- `--allow-stub` explicitly allows fallback/stub runs (good for plumbing tests, bad for evidence-quality data).
- Debater EV guard knobs can be tuned per debater in config:
  - `ev_guard_enabled`
  - `ev_guard_min_ev`
  - `ev_guard_edge_scale`
  - `low_balance_threshold`
  - `low_balance_bet_cap`

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

Strict run with judge gate:

```bash
python demo_tournament.py --config configs/tournament_config.yaml --gate-judge-variance
```

Recommended vLLM scale run:

```bash
set VLLM_BASE_URL=http://localhost:8000
python demo_tournament.py --config configs/vllm_tournament_recommended.yaml --gate-judge-variance
```

Experimental multi-agent injection run:

```bash
python demo_tournament.py --config configs/multi_agent_experimental.yaml --gate-judge-variance
```

One-command vLLM pipeline (start server, wait, gate, tournament, logs):

```bash
powershell -ExecutionPolicy Bypass -File scripts/run_vllm_research.ps1
```

OpenAI-compatible benchmark pipeline (PowerShell):

```bash
powershell -ExecutionPolicy Bypass -File scripts/run_phase1_openai_compat.ps1
```

This command now also writes a compact summary JSON:
- `logs/vllm_research_summary_<timestamp>.json`
- `logs/selection_health_dashboard_<timestamp>.json`

Standalone dashboard command:

```bash
python tests/selection_health_dashboard.py --transcript logs/tournament_results_transcript.json --results logs/tournament_results.json --ledger logs/tournament_results_ledger.json
```

Options:
- `--variance-runs` (default 10)
- `--max-judge-stdev` (default 0.05)
- `--min-judge-mean-a` (default 0.55)

## Experiment Scripts

- Judge variance report:

```bash
python tests/stress_judge_variance.py --model ollama:qwen2.5:1.5b
```

- Baseline vs economy paired run:

```bash
python tests/reproduce_baseline_vs_economy.py --config configs/tournament_config.yaml
```

- Multi-agent ON/OFF paired ablation:

```bash
python tests/reproduce_multi_agent_ablation.py --config configs/multi_agent_experimental.yaml --seeds 101,202,303 --rounds 3
```

- Economy parameter derivation:

```bash
python tests/derive_economy_params.py --survival-rounds 6 --avg-generation-cost 30 --avg-bet-size 20
```

## Phase 1 Benchmark Procedure

Single strict benchmark run:

```bash
python tests/run_phase1_benchmark.py --config configs/benchmark_phase1.yaml --tournament-config configs/ollama_tournament_recommended.yaml --model-id ollama:qwen2.5:7b --judge-model ollama:qwen2.5:7b --seeds 101
```

Batch benchmark run:

```bash
python scripts/run_phase1_batch.py --config configs/benchmark_phase1.yaml --tournament-config configs/ollama_tournament_recommended.yaml --model-id ollama:qwen2.5:7b --judge-model ollama:qwen2.5:7b --seeds 101,202,303 --matrix-labels set01
```

Massive tournament dataset run (per-run archives + trace JSONL):

```bash
python scripts/run_tournament_batch.py --config configs/ollama_tournament_50r_dataset.yaml --runs 50 --start-seed 101 --variance-runs 10 --min-calibration-pass-rate 0.67
```

Useful flags:
- `--source-mode`: `default | core_live_stretch_fixture | all_live | all_fixture`
- `--enable-model-derived-metrics` (on `tests/run_phase1_benchmark.py`)
- `--openai-base-urls`: endpoint roster for `openai:*` models (round-robin assignment across jobs)
- `--allow-stub` only for plumbing checks, never for claim-bearing evidence

## Output Artifacts

- Transcript JSON and Markdown
- Round/tournament summaries
- Ledger JSON with timestamped transactions
- Optional observer metrics and experiment reports under `logs/`
