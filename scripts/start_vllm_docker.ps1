param(
    [string]$Model = "Qwen/Qwen2.5-7B-Instruct",
    [int]$Port = 8000,
    [double]$GpuMemUtil = 0.9,
    [int]$MaxModelLen = 4096
)

$ErrorActionPreference = "Stop"

Write-Host "Starting vLLM in Docker..." -ForegroundColor Cyan
Write-Host "Model: $Model"
Write-Host "Port:  $Port"

# Requires NVIDIA Container Toolkit integration in Docker Desktop.
# On Windows, ensure Docker Desktop + WSL2 backend + GPU support are enabled.

docker run --rm --gpus all -p ${Port}:8000 `
  -e HF_HUB_ENABLE_HF_TRANSFER=1 `
  vllm/vllm-openai:latest `
  --model $Model `
  --host 0.0.0.0 `
  --port 8000 `
  --gpu-memory-utilization $GpuMemUtil `
  --max-model-len $MaxModelLen
