# AICampTownDebate

Adversarial token-economy debate for inference-time compute experiments.

VIDEO LINK https://streamable.com/m28985

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
- `openai:<model>`
- `stub`
- `<path-to-model.gguf>` (llama.cpp path mode)

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

Experimental multi-agent injection run (peer-draft critique/synthesis):

```bash
python demo_tournament.py --config configs/multi_agent_experimental.yaml --gate-judge-variance
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
powershell -ExecutionPolicy Bypass -File scripts/run_phase1_openai_compat.ps1
powershell -ExecutionPolicy Bypass -File scripts/run_e2e_smoke_pipeline.ps1
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

Multi-agent ON/OFF paired ablation:

```bash
python tests/reproduce_multi_agent_ablation.py --config configs/multi_agent_experimental.yaml --seeds 101,202,303 --rounds 3
```

Economy calibration from runway assumptions:

```bash
python tests/derive_economy_params.py --survival-rounds 6 --avg-generation-cost 30 --avg-bet-size 20
```

Tournament dashboard from transcript artifacts:

```bash
python src/analysis/tournament_html.py logs/tournament_results_transcript.json
```

Cross-session leaderboard (SQLite by default):

```bash
python tests/show_leaderboard.py --stats
```

## Phase 1 Benchmark

Single run:

```bash
python tests/run_phase1_benchmark.py --config configs/benchmark_phase1.yaml --tournament-config configs/ollama_tournament_recommended.yaml --model-id ollama:qwen2.5:7b --judge-model ollama:qwen2.5:7b --seeds 101
```

Batch run:

```bash
python scripts/run_phase1_batch.py --config configs/benchmark_phase1.yaml --tournament-config configs/ollama_tournament_recommended.yaml --model-id ollama:qwen2.5:7b --judge-model ollama:qwen2.5:7b --seeds 101,202,303
```

Massive tournament dataset batch (strict 7B, archived per run):

```bash
python scripts/run_tournament_batch.py --config configs/ollama_tournament_50r_dataset.yaml --runs 50 --start-seed 101 --variance-runs 10 --min-calibration-pass-rate 0.67
```

Evolutionary benchmark campaign (mutate policy knobs + prompts, select elites):

```bash
python scripts/run_evolution_campaign.py --benchmark-config configs/benchmark_phase1.yaml --tournament-config configs/ollama_tournament_recommended.yaml --model-id ollama:qwen2.5:7b --judge-model ollama:qwen2.5:7b --generations 4 --population-size 8 --elite-count 3 --seeds 101,202 --enable-model-derived-metrics
```

Detached queue wrapper for long campaigns (avoids terminal/session timeout):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/queue_evolution_campaign.ps1 -Action start -ModelId ollama:qwen2.5:7b -JudgeModel ollama:qwen2.5:7b -Generations 6 -PopulationSize 10 -EliteCount 3
powershell -ExecutionPolicy Bypass -File scripts/queue_evolution_campaign.ps1 -Action status -QueueId <QUEUE_ID>
powershell -ExecutionPolicy Bypass -File scripts/queue_evolution_campaign.ps1 -Action stop -QueueId <QUEUE_ID>
```

Autopilot staged evolution (auto-promote best config between stages):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/auto_evolution_stages.ps1 -Profile standard -ModelId ollama:qwen2.5:7b -JudgeModel ollama:qwen2.5:7b -EnableModelDerivedMetrics
```

Profiles:
- `fast`: quick smoke of stage chaining
- `standard`: balanced unattended run
- `deep`: long multi-stage run for stronger search pressure

Summarize and rank all evolution campaign outputs:

```bash
python scripts/summarize_evolution_runs.py --top 20
```

One-command smoke pipeline (benchmark -> submission packet -> training data):

```bash
powershell -ExecutionPolicy Bypass -File scripts/run_e2e_smoke_pipeline.ps1
```

## Documentation

- `CONCEPT.md`: theory and goals
- `DEVLOG.md`: recent implementation log
- `docs/architecture.md`: architecture and module map
- `docs/PROCEDURES.md`: reproducible run procedure
- `docs/ECONOMIC_ANALYSIS.md`: economic assumptions and math notes
- `docs/BENCHMARK_PROTOCOL.md`: phase-1 benchmark policy and pass/fail semantics
- `docs/EVALUATION_CONTRACT.md`: claim-level and provenance requirements
- `docs/INTEL_AND_CLOUD_RUNTIME.md`: OpenAI-compatible (`openai:`) runtime path
- `docs/NEXT_AI_BOOTSTRAP.md`: fast handoff checklist for the next run
