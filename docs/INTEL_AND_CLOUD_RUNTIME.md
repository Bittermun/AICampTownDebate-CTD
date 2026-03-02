# Intel + Cloud Runtime Path

This project now supports a portable `openai:` model prefix so the same benchmark/tournament
pipeline can run against:

- Local OpenAI-compatible endpoints (including Intel-oriented local stacks)
- Remote paid GPU endpoints (vLLM/OpenAI-compatible providers)

## 1) Model ID format

Use:

`openai:<model-id>`

Examples:

- `openai:Qwen/Qwen2.5-1.5B-Instruct`
- `openai:meta-llama/Llama-3.1-8B-Instruct`

## 2) Required environment variables

- `OPENAI_COMPAT_BASE_URL` (default `http://localhost:8000`)
- `OPENAI_COMPAT_API_KEY` (optional, when endpoint requires auth)
- `OPENAI_COMPAT_MODEL` (optional default model)

## 3) Quick local run (PowerShell)

```powershell
.\scripts\run_phase1_openai_compat.ps1 `
  -BaseUrl "http://localhost:8000" `
  -Model "Qwen/Qwen2.5-1.5B-Instruct" `
  -SourceMode "all_fixture" `
  -Seeds "101,202,303" `
  -Concurrency 1
```

## 4) Direct batch command (portable)

```powershell
$env:OPENAI_COMPAT_BASE_URL="http://localhost:8000"
python scripts/run_phase1_batch.py `
  --config configs/benchmark_phase1.yaml `
  --tournament-config configs/openai_compat_tournament_recommended.yaml `
  --model-id openai:Qwen/Qwen2.5-1.5B-Instruct `
  --judge-model openai:Qwen/Qwen2.5-1.5B-Instruct `
  --source-mode all_fixture `
  --seeds 101,202,303 `
  --matrix-labels set01 `
  --concurrency 1
```

## 5) Switching to paid GPU later

Only change endpoint + model:

- `OPENAI_COMPAT_BASE_URL` -> your provider URL
- `OPENAI_COMPAT_API_KEY` -> provider key
- `openai:<model-id>` -> hosted model id

No benchmark code changes needed.
