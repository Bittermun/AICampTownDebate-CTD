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
- `OPENAI_COMPAT_API_VERSION` (`auto` by default; supported: `auto | v1 | v3`)
- `OPENAI_COMPAT_HEALTHCHECK_TTL_SEC` (default `30`; reduces per-request health checks)

`OPENAI_COMPAT_API_VERSION=auto` now probes both `/v1` and `/v3` style endpoints, which
helps with Intel OpenVINO Model Server (`/v3`) and standard OpenAI-compatible servers (`/v1`).

## 3) Quick local run (PowerShell)

```powershell
.\scripts\run_phase1_openai_compat.ps1 `
  -BaseUrl "http://localhost:8000" `
  -ApiVersion "auto" `
  -Model "Qwen/Qwen2.5-1.5B-Instruct" `
  -SourceMode "all_fixture" `
  -Seeds "101,202,303" `
  -Concurrency 1
```

## 4) Direct batch command (portable)

```powershell
$env:OPENAI_COMPAT_BASE_URL="http://localhost:8000"
$env:OPENAI_COMPAT_API_VERSION="auto"
python scripts/run_phase1_batch.py `
  --config configs/benchmark_phase1.yaml `
  --tournament-config configs/openai_compat_tournament_recommended.yaml `
  --model-id openai:Qwen/Qwen2.5-1.5B-Instruct `
  --judge-model openai:Qwen/Qwen2.5-1.5B-Instruct `
  --source-mode all_fixture `
  --seeds 101,202,303 `
  --matrix-labels set01 `
  --concurrency 1 `
  --openai-base-urls http://localhost:8000
```

## 5) Intel parallel inference guidance

- Arc GPU path (`TargetDevice=arc_gpu`): use endpoint-side batching plus project concurrency (`--concurrency 2-4`), then tune upward while watching latency/VRAM.
- NPU path (`TargetDevice=npu`): start with `--concurrency 1`; scale only after validating stability/latency.
- Mixed hardware strategy: pass multiple endpoints with `--openai-base-urls` (or `-OpenAIBaseUrls`) and the batch runner will assign jobs round-robin.
- For OVMS/OpenVINO endpoints, keep `OPENAI_COMPAT_API_VERSION=auto` unless your deployment requires forcing `v3`.

PowerShell helper example:

```powershell
.\scripts\run_phase1_openai_compat.ps1 `
  -BaseUrl "http://arc-host:8000" `
  -SecondaryBaseUrl "http://npu-host:8000" `
  -ApiVersion "auto" `
  -TargetDevice "arc_npu" `
  -Concurrency 3
```

## 6) Switching to paid GPU later

Only change endpoint + model:

- `OPENAI_COMPAT_BASE_URL` -> your provider URL
- `OPENAI_COMPAT_API_KEY` -> provider key
- `openai:<model-id>` -> hosted model id

No benchmark code changes needed.
