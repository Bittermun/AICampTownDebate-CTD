# Intel GPU/NPU Parallel Inference Investigation (2026-03-02)

## Scope

Investigate how to connect Intel GPU/NPU acceleration to this repository's batch benchmark flow:

- `scripts/run_phase1_batch.py`
- `tests/run_phase1_benchmark.py`
- `src/models/openai_compat_backend.py`
- `src/arena/dynamic_round.py`

## Local hardware snapshot (this workstation)

From Windows device queries on 2026-03-02:

- `Intel(R) Arc(TM) Graphics` (driver `32.0.101.5542`)
- `Intel(R) AI Boost` (NPU, class `ComputeAccelerator`)

Current Python env checks:

- `torch`: installed
- `openvino`: not installed
- `openvino_genai`: not installed
- `intel_extension_for_pytorch`: not installed
- `ipex_llm`: not installed

## Project bottlenecks relevant to Intel acceleration

1. Batch-level parallelism exists: `scripts/run_phase1_batch.py` uses `ThreadPoolExecutor` to run multiple seed jobs.
2. Runtime path for Intel servers exists: project supports `openai:<model-id>` endpoint routing.
3. Per-request overhead existed in `openai_compat_backend`: health checks happened repeatedly.
4. Opening argument generation had an async path but was not activated in the main round run path.

## Changes made in this investigation

1. `src/models/openai_compat_backend.py`
   - Added automatic endpoint discovery for both `/v1` and `/v3` APIs.
   - Added session reuse plus health-check TTL caching (`OPENAI_COMPAT_HEALTHCHECK_TTL_SEC`).
   - Added `OPENAI_COMPAT_API_VERSION` (`auto|v1|v3`) for explicit routing control.

2. `scripts/run_phase1_batch.py`
   - Added `--openai-base-urls` endpoint roster support for `openai:*` runs.
   - Jobs are assigned to endpoints round-robin and each subprocess receives its own `OPENAI_COMPAT_BASE_URL`.
   - Batch manifests and JSONL records now include assigned endpoint URL per run.

3. `src/models/debater.py`
   - Enabled async generation path for `openai_compat` backend.

4. `src/arena/dynamic_round.py`
   - Activated parallel opening generation when both debaters run on API backends (`ollama|vllm|openai_compat`), with sync fallback.

5. `scripts/run_phase1_openai_compat.ps1`
   - Added `-ApiVersion`, `-HealthcheckTtlSec`, and `-TargetDevice` knobs.
   - Added endpoint roster inputs (`-SecondaryBaseUrl`, `-OpenAIBaseUrls`) for Arc+NPU sharding.

6. `docs/INTEL_AND_CLOUD_RUNTIME.md`
   - Documented the new endpoint-version and healthcheck settings.
   - Added Intel-targeted concurrency plus multi-endpoint sharding guidance.

## Practical operating guidance for this repo

1. Start with OpenAI-compatible endpoint mode (`openai:` models) and keep batch orchestration unchanged.
2. For Arc GPU endpoints, start `--concurrency 2` and tune upward.
3. For NPU endpoints, start `--concurrency 1`; increase only if latency/throughput remains stable.
4. For Arc + NPU true parallel utilization, pass both endpoints in `--openai-base-urls` (or `-OpenAIBaseUrls`) and run a single batch invocation.

## Quick command

```powershell
.\scripts\run_phase1_openai_compat.ps1 `
  -BaseUrl "http://arc-host:8000" `
  -SecondaryBaseUrl "http://npu-host:8000" `
  -ApiVersion "auto" `
  -TargetDevice "arc_npu" `
  -Model "Qwen/Qwen2.5-1.5B-Instruct" `
  -Seeds "101,202,303" `
  -Concurrency 3
```
