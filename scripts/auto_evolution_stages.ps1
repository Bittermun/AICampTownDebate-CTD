param(
    [ValidateSet("fast", "standard", "deep")]
    [string]$Profile = "standard",
    [string]$BenchmarkConfig = "configs/benchmark_phase1.yaml",
    [string]$TournamentConfig = "configs/ollama_tournament_recommended.yaml",
    [string]$ModelId = "ollama:qwen2.5:7b",
    [string]$JudgeModel = "ollama:qwen2.5:7b",
    [ValidateSet("default", "core_live_stretch_fixture", "all_live", "all_fixture")]
    [string]$SourceMode = "all_fixture",
    [double]$MutationPower = 1.0,
    [int]$RngSeed = 17,
    [string]$OutputDir = "logs",
    [int]$PollSeconds = 60,
    [int]$StageTimeoutHours = 6,
    [int]$StageHardLimitHours = 14,
    [int]$ProgressGraceMinutes = 30,
    [switch]$AllowStub,
    [switch]$DryRun,
    [switch]$EnableModelDerivedMetrics
)

$ErrorActionPreference = "Stop"

function Get-StagePlan {
    param([string]$Name)
    switch ($Name) {
        "fast" {
            return @(
                @{ Name = "s1"; Generations = 1; Population = 2; Elite = 1; Seeds = "101"; NumRounds = 2; MaxIterations = 2; JudgeVarianceRuns = 2; DisableCalibrationGate = $true },
                @{ Name = "s2"; Generations = 1; Population = 3; Elite = 1; Seeds = "101"; NumRounds = 3; MaxIterations = 2; JudgeVarianceRuns = 2; DisableCalibrationGate = $true }
            )
        }
        "deep" {
            return @(
                @{ Name = "s1"; Generations = 3; Population = 4; Elite = 2; Seeds = "101,202"; NumRounds = 6; MaxIterations = 4; JudgeVarianceRuns = 3; DisableCalibrationGate = $true },
                @{ Name = "s2"; Generations = 4; Population = 6; Elite = 2; Seeds = "101,202"; NumRounds = 8; MaxIterations = 5; JudgeVarianceRuns = 5; JudgeCalibrationMinPassRate = 0.67 },
                @{ Name = "s3"; Generations = 5; Population = 8; Elite = 3; Seeds = "101,202,303"; NumRounds = 10; MaxIterations = 5; JudgeVarianceRuns = 8; JudgeCalibrationMinPassRate = 0.72 },
                @{ Name = "s4"; Generations = 6; Population = 10; Elite = 3; Seeds = "101,202,303"; NumRounds = 12; MaxIterations = 6 }
            )
        }
        default {
            return @(
                @{ Name = "s1"; Generations = 2; Population = 4; Elite = 2; Seeds = "101"; NumRounds = 4; MaxIterations = 3; JudgeVarianceRuns = 3; DisableCalibrationGate = $true },
                @{ Name = "s2"; Generations = 3; Population = 5; Elite = 2; Seeds = "101,202"; NumRounds = 6; MaxIterations = 4; JudgeVarianceRuns = 5; JudgeCalibrationMinPassRate = 0.67 },
                @{ Name = "s3"; Generations = 4; Population = 7; Elite = 3; Seeds = "101,202"; NumRounds = 8; MaxIterations = 5 }
            )
        }
    }
}

function Get-DescendantProcessIds {
    param([int]$ParentId)
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ParentId" -ErrorAction SilentlyContinue
    $ids = @()
    foreach ($c in $children) {
        $ids += [int]$c.ProcessId
        $ids += Get-DescendantProcessIds -ParentId ([int]$c.ProcessId)
    }
    return $ids
}

function Stop-ProcessTree {
    param([int]$RootPid)
    $ids = @($RootPid) + @(Get-DescendantProcessIds -ParentId $RootPid)
    $ids = $ids | Sort-Object -Unique -Descending
    foreach ($id in $ids) {
        $p = Get-Process -Id $id -ErrorAction SilentlyContinue
        if ($p) {
            try { Stop-Process -Id $id -Force -ErrorAction Stop } catch {}
        }
    }
}

function Wait-QueueCompletion {
    param(
        [string]$QueueId,
        [string]$QueueRoot,
        [int]$PollSec,
        [int]$TimeoutHours,
        [int]$HardLimitHours,
        [int]$GraceMinutes
    )
    $metaPath = Join-Path $QueueRoot "$QueueId\meta.json"
    if (-not (Test-Path $metaPath)) {
        throw "Queue meta not found: $metaPath"
    }
    $meta = Get-Content -Raw -Path $metaPath | ConvertFrom-Json
    $procId = [int]$meta.pid
    $logPath = [string]$meta.log
    $stageStart = Get-Date
    $softDeadline = $stageStart.AddHours($TimeoutHours)
    $hardDeadline = $stageStart.AddHours($HardLimitHours)

    while ($true) {
        $now = Get-Date
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        $isRunning = $null -ne $proc
        if (-not $isRunning) {
            Write-Host "[auto] queue $QueueId completed."
            return $logPath
        }

        $elapsedMin = [int](($now - $stageStart).TotalMinutes)
        Write-Host "[auto] queue $QueueId running (pid=$procId, elapsed=${elapsedMin}m)."

        $logIsFresh = $false
        if (Test-Path $logPath) {
            $tail = Get-Content -Path $logPath -Tail 3
            if ($tail) {
                Write-Host "[auto] tail:"
                $tail | ForEach-Object { Write-Host "  $_" }
            }
            $lastWrite = (Get-Item $logPath).LastWriteTime
            $staleMin = ($now - $lastWrite).TotalMinutes
            $logIsFresh = $staleMin -le $GraceMinutes
            Write-Host ("[auto] log_last_write=" + $lastWrite.ToString("o") + " stale_min=" + [math]::Round($staleMin,1))
        }

        if ($now -gt $hardDeadline) {
            Write-Host "[auto][warn] queue $QueueId hit hard limit (${HardLimitHours}h); stopping process tree rooted at PID=$procId"
            Stop-ProcessTree -RootPid $procId
            throw "Queue $QueueId exceeded hard limit of $HardLimitHours hours"
        }

        if ($now -gt $softDeadline) {
            if ($logIsFresh) {
                $softDeadline = $now.AddHours(1)
                Write-Host "[auto][warn] queue $QueueId passed soft timeout but log is active; extending soft timeout by 1h."
            }
            else {
                Write-Host "[auto][warn] queue $QueueId passed soft timeout and appears stalled; stopping process tree rooted at PID=$procId"
                Stop-ProcessTree -RootPid $procId
                throw "Queue $QueueId exceeded soft timeout of $TimeoutHours hours with stale logs"
            }
        }
        Start-Sleep -Seconds $PollSec
    }
}

function Resolve-CampaignReport {
    param(
        [string]$LogPath,
        [datetime]$StageStart
    )
    if (Test-Path $LogPath) {
        $match = Select-String -Path $LogPath -Pattern "^Campaign report:\s*(.+)$" | Select-Object -Last 1
        if ($match) {
            $campaignDir = $match.Matches[0].Groups[1].Value.Trim()
            $report = Join-Path $campaignDir "campaign_report.json"
            if (Test-Path $report) {
                return $report
            }
        }
    }

    $fallback = Get-ChildItem -Path "logs" -Directory -Filter "evolution_campaign_*" |
        Where-Object { $_.LastWriteTime -ge $StageStart.AddMinutes(-2) } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($fallback) {
        $report = Join-Path $fallback.FullName "campaign_report.json"
        if (Test-Path $report) {
            return $report
        }
    }
    return ""
}

$runId = "auto_evo_" + (Get-Date -Format "yyyyMMdd_HHmmss")
$queueRoot = Join-Path "logs" "queue_evolution"
$manifestPath = Join-Path "logs" "$runId`_manifest.json"
$stages = Get-StagePlan -Name $Profile

$manifest = [ordered]@{
    run_id = $runId
    started_at = (Get-Date).ToString("o")
    profile = $Profile
    benchmark_config = $BenchmarkConfig
    model_id = $ModelId
    judge_model = $JudgeModel
    source_mode = $SourceMode
    dry_run = [bool]$DryRun
    allow_stub = [bool]$AllowStub
    enable_model_derived_metrics = [bool]$EnableModelDerivedMetrics
    stages = @()
}

$currentConfig = $TournamentConfig

foreach ($stage in $stages) {
    $stageStart = Get-Date
    $queueId = "$runId" + "_" + $stage.Name
    Write-Host "[auto] starting stage $($stage.Name) with queue_id=$queueId"
    Write-Host "[auto] config=$currentConfig gens=$($stage.Generations) pop=$($stage.Population) elite=$($stage.Elite) seeds=$($stage.Seeds)"

    $cmd = @(
        "-ExecutionPolicy", "Bypass",
        "-File", "scripts/queue_evolution_campaign.ps1",
        "-Action", "start",
        "-QueueId", $queueId,
        "-BenchmarkConfig", $BenchmarkConfig,
        "-TournamentConfig", $currentConfig,
        "-ModelId", $ModelId,
        "-JudgeModel", $JudgeModel,
        "-Seeds", $stage.Seeds,
        "-Generations", "$($stage.Generations)",
        "-PopulationSize", "$($stage.Population)",
        "-EliteCount", "$($stage.Elite)",
        "-MutationPower", "$MutationPower",
        "-RngSeed", "$RngSeed",
        "-SourceMode", $SourceMode,
        "-NumRoundsOverride", "$($stage.NumRounds)",
        "-MaxIterationsOverride", "$($stage.MaxIterations)",
        "-OutputDir", $OutputDir
    )
    if ($AllowStub) { $cmd += "-AllowStub" }
    if ($DryRun) { $cmd += "-DryRun" }
    if ($EnableModelDerivedMetrics) { $cmd += "-EnableModelDerivedMetrics" }
    if ($stage.ContainsKey("JudgeVarianceRuns")) { $cmd += @("-JudgeVarianceRunsOverride", "$($stage.JudgeVarianceRuns)") }
    if ($stage.ContainsKey("JudgeCalibrationMinPassRate")) { $cmd += @("-JudgeCalibrationMinPassRateOverride", "$($stage.JudgeCalibrationMinPassRate)") }
    if ($stage.ContainsKey("DisableCalibrationGate") -and $stage.DisableCalibrationGate) { $cmd += "-DisableJudgeCalibrationGate" }

    & powershell @cmd | Out-Host
    $logPath = Wait-QueueCompletion -QueueId $queueId -QueueRoot $queueRoot -PollSec $PollSeconds -TimeoutHours $StageTimeoutHours -HardLimitHours $StageHardLimitHours -GraceMinutes $ProgressGraceMinutes
    $reportPath = Resolve-CampaignReport -LogPath $logPath -StageStart $stageStart

    if (-not $reportPath) {
        throw "Could not resolve campaign report for queue $queueId"
    }

    $report = Get-Content -Raw -Path $reportPath | ConvertFrom-Json
    $best = $report.best_candidate
    $bestConfig = [string]$report.best_candidate_config
    if (-not (Test-Path $bestConfig)) {
        throw "Best candidate config missing: $bestConfig"
    }

    $manifestStage = [ordered]@{
        name = $stage.Name
        queue_id = $queueId
        tournament_config_in = $currentConfig
        campaign_report = $reportPath
        best_candidate_config = $bestConfig
        best_fitness = [double]$best.fitness
        best_aggregate_score = [double]$best.aggregate_score
        best_win_rate_vs_incumbent = [double]$best.win_rate_vs_incumbent
        completed_at = (Get-Date).ToString("o")
    }
    $manifest.stages += $manifestStage
    $manifest | ConvertTo-Json -Depth 8 | Set-Content -Path $manifestPath -Encoding utf8

    Write-Host "[auto] stage $($stage.Name) complete: fitness=$($best.fitness) aggregate=$($best.aggregate_score)"
    $currentConfig = $bestConfig
}

$manifest.completed_at = (Get-Date).ToString("o")
$manifest.final_config = $currentConfig
$manifest | ConvertTo-Json -Depth 8 | Set-Content -Path $manifestPath -Encoding utf8

Write-Host "[auto] all stages complete."
Write-Host "[auto] manifest: $manifestPath"
Write-Host "[auto] final config: $currentConfig"
