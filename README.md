# AICampTownDebate

An adversarial token-economy debate arena for inference-time compute research.

## Vision

Two goals drive this project:

1. **Train a competitive model at lower cost.** Use evolutionary selection pressure and economic bankruptcy to generate high-quality training data (SFT + preference pairs) from small models debating under scarcity. The hypothesis: models that survive economic pressure develop better reasoning traces, and those traces can be distilled into a cheaper model that performs comparably to frontier systems.

2. **Observe emergent strategic behavior.** Rather than prescribing rules for how models should reason, this system creates an environment where economic pressure, judge feedback, and survival dynamics may produce emergent allocation intelligence — models learning when to think hard, when to conserve, and how to adapt after losses.

A core design principle is **non-arbitrariness**: every mechanism should be grounded in economics, information theory, or evolutionary dynamics rather than ad hoc penalties or hardcoded rules. If behavior is degenerate, the first question is whether the evaluation signal or incentive structure is broken — not whether to add a guard rail.

VIDEO LINK https://streamable.com/m28985

## What It Does

Two LLM debaters argue across rounds under a shared token economy:

- Every action costs tokens (generation, deliberation, search, summarization)
- Better-judged arguments earn tokens from a shared pot
- Debaters choose `RESPOND` (bet + counter-argue) or `PASS` (conserve) each iteration
- Bets are sized using Kelly criterion with EV guards
- Fees scale per iteration (5% to 50% cap), making uninformed aggression costly
- Bankruptcy eliminates a debater; survival requires strategic resource allocation
- Judges use multi-dimension scoring (accuracy/responsiveness/development) with positional bias mitigation

## Current State (Honest Assessment)

See `docs/PROJECT_STATUS.md` for detailed readiness scores.

**What works:**
- Core tournament loop runs end-to-end with real models (ollama, vllm, openai-compatible)
- Token economy with accounting audit checks
- Multi-dimension judging with variance/calibration gates
- Evolutionary campaign system (mutate strategy profiles, select winners)
- Config-driven experiments with strict/fallback modes
- Transcript and trace data export
- Cross-round strategy memory

**What's partial or stub:**
- Training data pipeline (generates SFT/preference data but no training loop consumes it)
- `src/economy/bank.py` — aspirational, will crash on import (missing dependency)
- Intel NPU runtime — essentially unstarted
- `src/arena/round.py` — dead code, superseded by `DynamicDebateRound`
- Trajectory parser uses fragile emoji-based markdown splitting

**Known bugs:**
- `tournament.py` winner-field logic (`self._eliminated is False` is never true — works by accident)

## Backends

Model strings use prefix routing:
- `ollama:<model>` — local Ollama server (fully functional)
- `vllm:<model>` — vLLM OpenAI-compatible endpoint (fully functional)
- `openai:<model>` — any OpenAI-compatible API (fully functional)
- `stub` — canned responses for plumbing tests (functional, not for research data)
- `<path-to-model.gguf>` — llama.cpp (partially functional, token counting broken)

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

**Quick single-round test:**

```bash
python demo_dynamic.py --config configs/tournament_config.yaml
```

**Tournament (recommended for research data):**

```bash
python demo_tournament.py --config configs/tournament_config.yaml --gate-judge-variance
```

**Single-round streaming visual (replay a saved round transcript):**

```bash
# Simplest (repo root)
.\run_viewer.ps1

# Specific round
.\run_viewer.ps1 -RoundId 1

# Auto-picks latest *_transcript.json in logs/
powershell -ExecutionPolicy Bypass -File scripts/run_round_stream_viewer.ps1 -RoundId 1

# Or explicitly choose a transcript + speed
powershell -ExecutionPolicy Bypass -File scripts/run_round_stream_viewer.ps1 `
  -TranscriptPath logs/archive/tournament_results_transcript.json `
  -RoundId 1 -Speed 1.5
```

Then open: `http://127.0.0.1:8787`

To stop the viewer:

```bash
Get-NetTCPConnection -LocalPort 8787 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

**Recommended Ollama scale-up:**

```bash
python demo_tournament.py --config configs/ollama_tournament_recommended.yaml --gate-judge-variance
```

**vLLM research tournament:**

```bash
set VLLM_BASE_URL=http://localhost:8000
python demo_tournament.py --config configs/vllm_tournament_recommended.yaml --gate-judge-variance
```

**Experimental multi-agent injection (peer-draft critique/synthesis):**

```bash
python demo_tournament.py --config configs/multi_agent_experimental.yaml --gate-judge-variance
```

**Development fallback (allows stub, not valid for research data):**

```bash
python demo_tournament.py --config configs/tournament_config.yaml --allow-stub
```

## Experiment Utilities

```bash
# Judge variance stress test
python tests/stress_judge_variance.py --model ollama:qwen2.5:1.5b

# Baseline vs economy comparison
python tests/reproduce_baseline_vs_economy.py --config configs/tournament_config.yaml

# Multi-agent ON/OFF ablation
python tests/reproduce_multi_agent_ablation.py --config configs/multi_agent_experimental.yaml --seeds 101,202,303 --rounds 3

# Economy parameter calibration
python tests/derive_economy_params.py --survival-rounds 6 --avg-generation-cost 30 --avg-bet-size 20

# Tournament HTML dashboard
python src/analysis/tournament_html.py logs/tournament_results_transcript.json

# Cross-session leaderboard
python tests/show_leaderboard.py --stats
```

## Benchmark and Evolution

```bash
# Single benchmark run
python tests/run_phase1_benchmark.py --config configs/benchmark_phase1.yaml \
  --tournament-config configs/ollama_tournament_recommended.yaml \
  --model-id ollama:qwen2.5:7b --judge-model ollama:qwen2.5:7b --seeds 101

# Batch benchmark
python scripts/run_phase1_batch.py --config configs/benchmark_phase1.yaml \
  --tournament-config configs/ollama_tournament_recommended.yaml \
  --model-id ollama:qwen2.5:7b --judge-model ollama:qwen2.5:7b --seeds 101,202,303

# Evolutionary campaign (mutate policy + prompts, select elites)
python scripts/run_evolution_campaign.py --benchmark-config configs/benchmark_phase1.yaml \
  --tournament-config configs/ollama_tournament_recommended.yaml \
  --model-id ollama:qwen2.5:7b --judge-model ollama:qwen2.5:7b \
  --generations 4 --population-size 8 --elite-count 3 --seeds 101,202 \
  --enable-model-derived-metrics

# Summarize evolution results
python scripts/summarize_evolution_runs.py --top 20
```

## One-Command Pipelines (PowerShell)

```bash
# vLLM research pipeline (start server, gate, tournament, archive)
powershell -ExecutionPolicy Bypass -File scripts/run_vllm_research.ps1

# End-to-end smoke (benchmark -> submission packet -> training data)
powershell -ExecutionPolicy Bypass -File scripts/run_e2e_smoke_pipeline.ps1

# Autopilot staged evolution
powershell -ExecutionPolicy Bypass -File scripts/auto_evolution_stages.ps1 \
  -Profile standard -ModelId ollama:qwen2.5:7b -JudgeModel ollama:qwen2.5:7b
```

## Documentation

| Doc | What it covers |
|-----|----------------|
| `CONCEPT.md` | Theory, design philosophy, and goals |
| `docs/PROJECT_STATUS.md` | Honest readiness assessment with gap analysis |
| `DEVLOG.md` | Session-by-session implementation log |
| `HANDOFF.md` | Fast orientation for new contributors |
| `AGENT_FORUM.md` | Multi-agent strategic discussion and insights |
| `docs/architecture.md` | Module map with active/dead code annotations |
| `docs/PROCEDURES.md` | Reproducible run procedures |
| `docs/ECONOMIC_ANALYSIS.md` | Economy math and calibration workflow |
| `docs/BENCHMARK_PROTOCOL.md` | Phase-1 benchmark policy |
| `docs/EVALUATION_CONTRACT.md` | Claim-level and provenance requirements |
