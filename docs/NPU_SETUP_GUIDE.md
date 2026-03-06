# Intel NPU/Arc GPU Setup Guide

This guide covers setting up Intel hardware acceleration for running debate tournaments.

## Hardware Detected on This Machine

- Intel Arc Graphics (driver 32.0.101.5542)
- Intel AI Boost (NPU, ComputeAccelerator class)
- Both can serve models via OpenVINO Model Server

## Architecture

The project doesn't need a native NPU backend. Instead:
1. **OpenVINO Model Server (OVMS)** serves the model on NPU/Arc hardware
2. OVMS exposes an OpenAI-compatible API (`/v1` or `/v3`)
3. The project's `openai_compat` backend connects to it

This means: install OVMS, convert the model, serve it, point the project at it.

## Step-by-Step Setup

### 1. Install Intel Dependencies

```powershell
# OpenVINO runtime + GenAI
pip install openvino openvino-genai

# Optional: Intel Extension for PyTorch (for training on Arc GPU)
pip install intel-extension-for-pytorch

# Optional: IPEX-LLM (optimized LLM inference for Intel)
pip install ipex-llm
```

### 2. Convert Model to OpenVINO Format

```powershell
# Convert Qwen2.5-1.5B to OpenVINO IR format
optimum-cli export openvino --model Qwen/Qwen2.5-1.5B-Instruct --task text-generation-with-past models/qwen2.5-1.5b-ov

# For INT4 quantization (smaller, faster on NPU):
optimum-cli export openvino --model Qwen/Qwen2.5-1.5B-Instruct --task text-generation-with-past --weight-format int4 models/qwen2.5-1.5b-ov-int4
```

### 3. Serve with OpenVINO Model Server

**Option A: Docker (recommended)**

```powershell
docker run -d --name ovms `
  -v ${PWD}/models:/models `
  -p 8000:8000 `
  openvino/model_server:latest `
  --model_path /models/qwen2.5-1.5b-ov `
  --model_name qwen2.5-1.5b `
  --port 8000 `
  --target_device NPU
```

**Option B: Direct Python serving**

```python
# serve_npu.py
from openvino_genai import LLMPipeline
from fastapi import FastAPI
import uvicorn

pipe = LLMPipeline("models/qwen2.5-1.5b-ov", device="NPU")
app = FastAPI()

@app.post("/v1/chat/completions")
async def chat(request: dict):
    messages = request.get("messages", [])
    prompt = messages[-1]["content"] if messages else ""
    result = pipe.generate(prompt, max_new_tokens=request.get("max_tokens", 256))
    return {
        "choices": [{"message": {"content": result}}],
        "usage": {"completion_tokens": len(result.split())}
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 4. Run Tournaments on NPU

```powershell
# Set endpoint
$env:OPENAI_COMPAT_BASE_URL = "http://localhost:8000"
$env:OPENAI_COMPAT_API_VERSION = "auto"

# Run tournament
python demo_tournament.py `
  --config configs/openai_compat_tournament_recommended.yaml `
  --gate-judge-variance

# Or use the batch runner
python scripts/run_phase1_batch.py `
  --config configs/benchmark_phase1.yaml `
  --tournament-config configs/openai_compat_tournament_recommended.yaml `
  --model-id openai:qwen2.5-1.5b `
  --judge-model openai:qwen2.5-1.5b `
  --seeds 101,202,303 `
  --concurrency 1
```

### 5. Mixed Hardware (Arc GPU + NPU)

If you want to use both simultaneously:

```powershell
# Start Arc GPU endpoint on port 8000
# Start NPU endpoint on port 8001

python scripts/run_phase1_batch.py `
  --openai-base-urls http://localhost:8000,http://localhost:8001 `
  --concurrency 2
```

The batch runner assigns jobs round-robin across endpoints.

## Performance Expectations

| Hardware | Model | Expected Tokens/sec | Notes |
|----------|-------|--------------------:|-------|
| RTX 4070 (Ollama) | qwen2.5:1.5b | ~60-80 | Current baseline |
| RTX 4070 (Ollama) | qwen2.5:7b | ~15-25 | Recommended judge model |
| Intel Arc (OpenVINO) | qwen2.5-1.5b-int4 | ~30-50 | Needs validation |
| Intel NPU | qwen2.5-1.5b-int4 | ~10-30 | Needs validation, start with concurrency=1 |

Performance numbers are estimates. Validate with a quick smoke run before committing to long tournaments.

## Troubleshooting

- **NPU not detected**: Check `Device Manager > Compute Accelerators > Intel AI Boost`
- **OVMS won't start**: Ensure Docker has access to the NPU device. On Windows, WSL2 with GPU passthrough may be needed.
- **Slow inference**: Try INT4 quantization. NPU is optimized for quantized models.
- **API version mismatch**: Set `OPENAI_COMPAT_API_VERSION=v3` for OVMS, `v1` for standard OpenAI endpoints.

## Current Status

**Architecture-ready, software not yet installed.** The `openai_compat` backend fully supports NPU-served models. What's missing is installing OpenVINO, converting a model, and validating end-to-end.

## Next Steps

1. Install `openvino` and `openvino-genai`
2. Convert qwen2.5-1.5b to OpenVINO IR format
3. Run a single-round smoke test on NPU
4. Benchmark tokens/sec and compare to Ollama baseline
5. If stable, run a full tournament for research data
