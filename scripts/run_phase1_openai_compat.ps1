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
    [string]$ApiKey = ""
)

$ErrorActionPreference = "Stop"

$env:OPENAI_COMPAT_BASE_URL = $BaseUrl
if ($ApiKey) { $env:OPENAI_COMPAT_API_KEY = $ApiKey }

$modelId = "openai:$Model"
$judgeId = if ($JudgeModel) { "openai:$JudgeModel" } else { $modelId }

Write-Host "OPENAI_COMPAT_BASE_URL=$env:OPENAI_COMPAT_BASE_URL"
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
  --output-dir $OutputDir

if ($LASTEXITCODE -ne 0) {
  throw "run_phase1_batch failed with exit code $LASTEXITCODE"
}
