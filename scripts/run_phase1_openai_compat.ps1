param(
    [string]$BaseUrl = "http://localhost:8000",
    [string]$Model = "Qwen/Qwen2.5-1.5B-Instruct",
    [string]$JudgeModel = "",
    [string]$Config = "configs/benchmark_phase1.yaml",
    [string]$TournamentConfig = "configs/openai_compat_tournament_recommended.yaml",
    [string]$Seeds = "101,202,303",
    [string]$MatrixLabels = "set01",
    [string]$SourceMode = "all_fixture",
    [int]$Concurrency = 1,
    [int]$BankruptcyRetries = 1,
    [string]$OutputDir = "logs/benchmark_batches",
    [string]$ApiKey = "",
    [ValidateSet("auto", "v1", "v3")]
    [string]$ApiVersion = "auto",
    [int]$HealthcheckTtlSec = 30,
    [ValidateSet("custom", "arc_gpu", "npu", "arc_npu")]
    [string]$TargetDevice = "custom",
    [string]$SecondaryBaseUrl = "",
    [string]$OpenAIBaseUrls = ""
)

$ErrorActionPreference = "Stop"

$env:OPENAI_COMPAT_BASE_URL = $BaseUrl
if ($ApiKey) { $env:OPENAI_COMPAT_API_KEY = $ApiKey }
$env:OPENAI_COMPAT_API_VERSION = $ApiVersion
$env:OPENAI_COMPAT_HEALTHCHECK_TTL_SEC = "$HealthcheckTtlSec"

if ($TargetDevice -eq "arc_gpu" -and $Concurrency -lt 2) {
  Write-Host "[hint] Arc GPU profile usually benefits from Concurrency >= 2."
}
if ($TargetDevice -eq "npu" -and $Concurrency -gt 1) {
  Write-Host "[hint] NPU profile is often best with Concurrency = 1."
}

$endpointRoster = $OpenAIBaseUrls
if (-not $endpointRoster) {
  if ($SecondaryBaseUrl) {
    $endpointRoster = "$BaseUrl,$SecondaryBaseUrl"
  } else {
    $endpointRoster = $BaseUrl
  }
}

$endpointCount = @($endpointRoster.Split(",") | Where-Object { $_.Trim() }).Count
if ($TargetDevice -eq "arc_npu" -and $endpointCount -lt 2) {
  Write-Host "[hint] arc_npu profile works best with at least two endpoints in -OpenAIBaseUrls."
}
if ($endpointCount -gt 1 -and $Concurrency -lt 2) {
  Write-Host "[hint] Multiple endpoints detected; consider Concurrency >= 2 to utilize both."
}

$modelId = "openai:$Model"
$judgeId = if ($JudgeModel) { "openai:$JudgeModel" } else { $modelId }

Write-Host "OPENAI_COMPAT_BASE_URL=$env:OPENAI_COMPAT_BASE_URL"
Write-Host "OPENAI_COMPAT_API_VERSION=$env:OPENAI_COMPAT_API_VERSION"
Write-Host "OPENAI_ENDPOINT_ROSTER=$endpointRoster"
Write-Host "Model: $modelId"
Write-Host "Judge: $judgeId"

python scripts/run_phase1_batch.py `
  --config $Config `
  --tournament-config $TournamentConfig `
  --model-id $modelId `
  --judge-model $judgeId `
  --seeds $Seeds `
  --matrix-labels $MatrixLabels `
  --source-mode $SourceMode `
  --concurrency $Concurrency `
  --bankruptcy-retries $BankruptcyRetries `
  --output-dir $OutputDir `
  --openai-base-urls $endpointRoster

if ($LASTEXITCODE -ne 0) {
  throw "run_phase1_batch failed with exit code $LASTEXITCODE"
}
