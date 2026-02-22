param(
    [string]$Config = "configs/benchmark_phase1.yaml",
    [string]$TournamentConfig = "configs/ollama_tournament_recommended.yaml",
    [string]$ModelId = "ollama:qwen2.5:7b",
    [string]$JudgeModel = "ollama:qwen2.5:7b",
    [string]$Seeds = "101",
    [string]$MatrixLabels = "set01",
    [string]$OutputDir = "logs/benchmark_batches",
    [string]$SourceMode = "core_live_stretch_fixture",
    [int]$Concurrency = 2,
    [int]$BankruptcyRetries = 1,
    [switch]$AllowStub,
    [switch]$RefreshLiveCache,
    [switch]$CacheOnlyLive
)

$ErrorActionPreference = "Stop"

$cmd = @(
    "scripts/run_phase1_batch.py",
    "--config", $Config,
    "--tournament-config", $TournamentConfig,
    "--model-id", $ModelId,
    "--judge-model", $JudgeModel,
    "--seeds", $Seeds,
    "--matrix-labels", $MatrixLabels,
    "--output-dir", $OutputDir,
    "--source-mode", $SourceMode,
    "--concurrency", "$Concurrency",
    "--bankruptcy-retries", "$BankruptcyRetries"
)

if ($AllowStub) { $cmd += "--allow-stub" }
if ($RefreshLiveCache) { $cmd += "--refresh-live-cache" }
if ($CacheOnlyLive) { $cmd += "--cache-only-live" }

python @cmd
if ($LASTEXITCODE -ne 0) {
    throw "Batch run failed with exit code $LASTEXITCODE"
}

