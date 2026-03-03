param(
    [ValidateSet("start", "status", "stop")]
    [string]$Action = "start",
    [string]$QueueId = "",
    [string]$BenchmarkConfig = "configs/benchmark_phase1.yaml",
    [string]$TournamentConfig = "configs/ollama_tournament_recommended.yaml",
    [string]$ModelId = "ollama:qwen2.5:7b",
    [string]$JudgeModel = "",
    [string]$Seeds = "101,202",
    [int]$Generations = 4,
    [int]$PopulationSize = 8,
    [int]$EliteCount = 3,
    [double]$MutationPower = 1.0,
    [int]$RngSeed = 17,
    [string]$FixturesDir = "benchmarks/fixtures",
    [ValidateSet("default", "core_live_stretch_fixture", "all_live", "all_fixture")]
    [string]$SourceMode = "core_live_stretch_fixture",
    [int]$NumRoundsOverride = 0,
    [int]$MaxIterationsOverride = 0,
    [int]$JudgeVarianceRunsOverride = 0,
    [double]$JudgeCalibrationMinPassRateOverride = 0,
    [string]$OutputDir = "logs",
    [switch]$AllowStub,
    [switch]$DryRun,
    [switch]$EnableModelDerivedMetrics,
    [switch]$DisableJudgeVarianceGate,
    [switch]$DisableJudgeCalibrationGate
)

$ErrorActionPreference = "Stop"
$queueRoot = Join-Path "logs" "queue_evolution"

function Get-QueuePaths {
    param([string]$Id)
    $jobDir = Join-Path $queueRoot $Id
    return @{
        JobDir = $jobDir
        Meta = Join-Path $jobDir "meta.json"
        Pid = Join-Path $jobDir "pid.txt"
        Log = Join-Path $jobDir "run.log"
        Err = Join-Path $jobDir "run.err.log"
    }
}

function Start-QueuedRun {
    if (-not $ModelId) {
        throw "ModelId is required for start."
    }

    New-Item -ItemType Directory -Force -Path $queueRoot | Out-Null
    $id = if ($QueueId) { $QueueId } else { "evo_" + (Get-Date -Format "yyyyMMdd_HHmmss") }
    $paths = Get-QueuePaths -Id $id
    New-Item -ItemType Directory -Force -Path $paths.JobDir | Out-Null

    $args = @(
        "scripts/run_evolution_campaign.py",
        "--benchmark-config", $BenchmarkConfig,
        "--tournament-config", $TournamentConfig,
        "--model-id", $ModelId,
        "--seeds", $Seeds,
        "--fixtures-dir", $FixturesDir,
        "--generations", "$Generations",
        "--population-size", "$PopulationSize",
        "--elite-count", "$EliteCount",
        "--mutation-power", "$MutationPower",
        "--rng-seed", "$RngSeed",
        "--source-mode", $SourceMode,
        "--output-dir", $OutputDir
    )
    if ($JudgeModel) { $args += @("--judge-model", $JudgeModel) }
    if ($AllowStub) { $args += "--allow-stub" }
    if ($DryRun) { $args += "--dry-run" }
    if ($EnableModelDerivedMetrics) { $args += "--enable-model-derived-metrics" }
    if ($NumRoundsOverride -gt 0) { $args += @("--num-rounds-override", "$NumRoundsOverride") }
    if ($MaxIterationsOverride -gt 0) { $args += @("--max-iterations-override", "$MaxIterationsOverride") }
    if ($JudgeVarianceRunsOverride -gt 0) { $args += @("--judge-variance-runs-override", "$JudgeVarianceRunsOverride") }
    if ($JudgeCalibrationMinPassRateOverride -gt 0) {
        $args += @("--judge-calibration-min-pass-rate-override", "$JudgeCalibrationMinPassRateOverride")
    }
    if ($DisableJudgeVarianceGate) { $args += "--disable-judge-variance-gate" }
    if ($DisableJudgeCalibrationGate) { $args += "--disable-judge-calibration-gate" }

    $quotedArgs = $args | ForEach-Object {
        if ($_ -match "\s") { '"' + $_ + '"' } else { $_ }
    }
    $command = "python -u " + ($quotedArgs -join " ")
    $argList = @("-u") + $args
    $proc = Start-Process -FilePath python -ArgumentList $argList -PassThru -WindowStyle Hidden -RedirectStandardOutput $paths.Log -RedirectStandardError $paths.Err
    Set-Content -Path $paths.Pid -Value $proc.Id -Encoding utf8

    $meta = [ordered]@{
        queue_id = $id
        started_at = (Get-Date).ToString("o")
        pid = $proc.Id
        status = "running"
        command = $command
        log = $paths.Log
        err_log = $paths.Err
        job_dir = $paths.JobDir
    }
    $meta | ConvertTo-Json -Depth 4 | Set-Content -Path $paths.Meta -Encoding utf8

    Write-Output "QUEUE_ID=$id"
    Write-Output "PID=$($proc.Id)"
    Write-Output "LOG=$($paths.Log)"
    Write-Output "ERR_LOG=$($paths.Err)"
    Write-Output "META=$($paths.Meta)"
}

function Show-Status {
    if (-not $QueueId) {
        throw "QueueId is required for status."
    }
    $paths = Get-QueuePaths -Id $QueueId
    if (-not (Test-Path $paths.Meta)) {
        throw "No queue metadata found for '$QueueId' at $($paths.Meta)"
    }

    $meta = Get-Content -Raw -Path $paths.Meta | ConvertFrom-Json
    $procId = [int]$meta.pid
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    $isRunning = $null -ne $proc
    $status = if ($isRunning) { "running" } else { "stopped" }

    Write-Output "QUEUE_ID=$QueueId"
    Write-Output "PID=$procId"
    Write-Output "STATUS=$status"
    Write-Output "LOG=$($meta.log)"
    if ($meta.PSObject.Properties.Name -contains "err_log") {
        Write-Output "ERR_LOG=$($meta.err_log)"
    }

    if (Test-Path $meta.log) {
        Write-Output ""
        Write-Output "----- tail($($meta.log)) -----"
        Get-Content -Path $meta.log -Tail 40
    }
    if (($meta.PSObject.Properties.Name -contains "err_log") -and (Test-Path $meta.err_log)) {
        $errSize = (Get-Item $meta.err_log).Length
        if ($errSize -gt 0) {
            Write-Output ""
            Write-Output "----- tail($($meta.err_log)) -----"
            Get-Content -Path $meta.err_log -Tail 40
        }
    }
}

function Stop-QueuedRun {
    if (-not $QueueId) {
        throw "QueueId is required for stop."
    }
    $paths = Get-QueuePaths -Id $QueueId
    if (-not (Test-Path $paths.Pid)) {
        throw "No pid file found for '$QueueId' at $($paths.Pid)"
    }
    $procId = [int](Get-Content -Raw -Path $paths.Pid).Trim()
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    if ($null -eq $proc) {
        Write-Output "QUEUE_ID=$QueueId"
        Write-Output "PID=$procId"
        Write-Output "STATUS=already_stopped"
        return
    }

    Stop-Process -Id $procId -Force
    Write-Output "QUEUE_ID=$QueueId"
    Write-Output "PID=$procId"
    Write-Output "STATUS=stopped"
}

switch ($Action) {
    "start" { Start-QueuedRun }
    "status" { Show-Status }
    "stop" { Stop-QueuedRun }
}
