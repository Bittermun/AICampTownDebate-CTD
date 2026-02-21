param(
    [string]$Config = "configs/vllm_tournament_recommended.yaml",
    [string]$Model = "Qwen/Qwen2.5-7B-Instruct",
    [int]$Port = 8000,
    [double]$GpuMemUtil = 0.9,
    [int]$MaxModelLen = 4096,
    [int]$ReadyTimeoutSec = 300,
    [int]$VarianceRuns = 10,
    [switch]$KeepContainer
)

$ErrorActionPreference = "Stop"

function Test-CommandExists {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

if (-not (Test-CommandExists "docker")) {
    throw "Docker is not installed or not on PATH."
}
if (-not (Test-CommandExists "python")) {
    throw "Python is not installed or not on PATH."
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$containerName = "aicamp_vllm_$timestamp"
$logDir = "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$runLog = Join-Path $logDir "vllm_research_run_$timestamp.log"
$summaryOut = Join-Path $logDir "vllm_research_summary_$timestamp.json"

$env:VLLM_BASE_URL = "http://localhost:$Port"

"[$(Get-Date -Format o)] Starting vLLM container '$containerName' on port $Port" | Tee-Object -FilePath $runLog -Append

$dockerArgs = @(
    "run", "-d", "--rm", "--gpus", "all",
    "--name", $containerName,
    "-p", "${Port}:8000",
    "vllm/vllm-openai:latest",
    "--model", $Model,
    "--host", "0.0.0.0",
    "--port", "8000",
    "--gpu-memory-utilization", "$GpuMemUtil",
    "--max-model-len", "$MaxModelLen"
)

$containerId = & docker @dockerArgs
if (-not $containerId) {
    throw "Failed to start vLLM container."
}

"[$(Get-Date -Format o)] Container started: $containerId" | Tee-Object -FilePath $runLog -Append

try {
    $deadline = (Get-Date).AddSeconds($ReadyTimeoutSec)
    $ready = $false

    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-RestMethod -Uri "$env:VLLM_BASE_URL/v1/models" -Method Get -TimeoutSec 5
            if ($resp.data) {
                $ready = $true
                break
            }
        } catch {
            Start-Sleep -Seconds 3
        }
    }

    if (-not $ready) {
        throw "vLLM did not become ready within $ReadyTimeoutSec seconds."
    }

    "[$(Get-Date -Format o)] vLLM ready at $env:VLLM_BASE_URL" | Tee-Object -FilePath $runLog -Append

    $testOut = Join-Path $logDir "judge_variance_vllm_$timestamp.json"
    "[$(Get-Date -Format o)] Running judge variance stress test" | Tee-Object -FilePath $runLog -Append
    & python tests/stress_judge_variance.py --model "vllm:$Model" --runs $VarianceRuns --output $testOut 2>&1 |
        Tee-Object -FilePath $runLog -Append
    if ($LASTEXITCODE -ne 0) {
        throw "Judge variance stress test failed."
    }

    "[$(Get-Date -Format o)] Running tournament with gate" | Tee-Object -FilePath $runLog -Append
    & python demo_tournament.py --config $Config --gate-judge-variance --variance-runs $VarianceRuns 2>&1 |
        Tee-Object -FilePath $runLog -Append
    if ($LASTEXITCODE -ne 0) {
        throw "Tournament run failed."
    }

    # Archive tournament outputs with timestamp
    $baseResults = Join-Path $logDir "tournament_results.json"
    $baseLedger = Join-Path $logDir "tournament_results_ledger.json"
    $baseTranscriptJson = Join-Path $logDir "tournament_results_transcript.json"
    $baseTranscriptMd = Join-Path $logDir "tournament_results_transcript.md"

    $runResults = Join-Path $logDir "tournament_results_$timestamp.json"
    $runLedger = Join-Path $logDir "tournament_results_ledger_$timestamp.json"
    $runTranscriptJson = Join-Path $logDir "tournament_results_transcript_$timestamp.json"
    $runTranscriptMd = Join-Path $logDir "tournament_results_transcript_$timestamp.md"

    if (Test-Path $baseResults) { Copy-Item $baseResults $runResults -Force }
    if (Test-Path $baseLedger) { Copy-Item $baseLedger $runLedger -Force }
    if (Test-Path $baseTranscriptJson) { Copy-Item $baseTranscriptJson $runTranscriptJson -Force }
    if (Test-Path $baseTranscriptMd) { Copy-Item $baseTranscriptMd $runTranscriptMd -Force }

    # Build compact summary JSON
    $resultsObj = $null
    if (Test-Path $baseResults) {
        $resultsObj = Get-Content -Raw $baseResults | ConvertFrom-Json
    }
    $varianceObj = $null
    if (Test-Path $testOut) {
        $varianceObj = Get-Content -Raw $testOut | ConvertFrom-Json
    }
    $transcriptObj = $null
    if (Test-Path $baseTranscriptJson) {
        $transcriptObj = Get-Content -Raw $baseTranscriptJson | ConvertFrom-Json
    }

    $winner = $null
    $balanceSpread = $null
    $meanAggressionA = $null
    $meanAggressionB = $null
    $meanPassA = $null
    $meanPassB = $null

    if ($resultsObj -and $resultsObj.final_balances) {
        $winner = $resultsObj.final_balances.PSObject.Properties |
            Sort-Object -Property Value -Descending |
            Select-Object -First 1 -ExpandProperty Name
        $balances = @($resultsObj.final_balances.PSObject.Properties | ForEach-Object { [double]$_.Value })
        if ($balances.Count -ge 2) {
            $sorted = $balances | Sort-Object -Descending
            $balanceSpread = [Math]::Round(($sorted[0] - $sorted[1]), 3)
        }
    }

    if ($transcriptObj -and $transcriptObj.rounds) {
        $aggA = @()
        $aggB = @()
        $passA = @()
        $passB = @()

        foreach ($round in $transcriptObj.rounds) {
            $dels = @($round.turns | Where-Object { $_.type -eq "deliberation" })
            if ($dels.Count -eq 0) { continue }
            $speakers = @($dels | Select-Object -ExpandProperty speaker -Unique)
            if ($speakers.Count -lt 2) { continue }

            $speakerA = $speakers[0]
            $speakerB = $speakers[1]

            $aTurns = @($dels | Where-Object { $_.speaker -eq $speakerA })
            $bTurns = @($dels | Where-Object { $_.speaker -eq $speakerB })

            $iterA = [Math]::Max(1, $aTurns.Count)
            $iterB = [Math]::Max(1, $bTurns.Count)

            $aPassCount = (@($aTurns | Where-Object { $_.content -match "\*\*Decision\*\*:\s*PASS" })).Count
            $bPassCount = (@($bTurns | Where-Object { $_.content -match "\*\*Decision\*\*:\s*PASS" })).Count
            $aRespondCount = $iterA - $aPassCount
            $bRespondCount = $iterB - $bPassCount

            $aggA += ($aRespondCount / $iterA)
            $aggB += ($bRespondCount / $iterB)
            $passA += ($aPassCount / $iterA)
            $passB += ($bPassCount / $iterB)
        }

        if ($aggA.Count -gt 0) {
            $meanAggressionA = [Math]::Round((($aggA | Measure-Object -Average).Average), 3)
            $meanAggressionB = [Math]::Round((($aggB | Measure-Object -Average).Average), 3)
            $meanPassA = [Math]::Round((($passA | Measure-Object -Average).Average), 3)
            $meanPassB = [Math]::Round((($passB | Measure-Object -Average).Average), 3)
        }
    }

    $summary = [ordered]@{
        timestamp = $timestamp
        config = $Config
        model = $Model
        vllm_base_url = $env:VLLM_BASE_URL
        winner = $winner
        balance_spread = $balanceSpread
        mean_aggression = @{
            debater_a = $meanAggressionA
            debater_b = $meanAggressionB
        }
        mean_pass_rate = @{
            debater_a = $meanPassA
            debater_b = $meanPassB
        }
        judge_variance = if ($varianceObj) {
            @{
                passed = $varianceObj.passed
                mean_confidence_a = $varianceObj.mean_confidence_a
                stdev_confidence_a = $varianceObj.stdev_confidence_a
                runs = $varianceObj.runs
            }
        } else { $null }
        artifacts = @{
            run_log = $runLog
            judge_variance_json = $testOut
            tournament_results_json = if (Test-Path $runResults) { $runResults } else { $baseResults }
            tournament_ledger_json = if (Test-Path $runLedger) { $runLedger } else { $baseLedger }
            tournament_transcript_json = if (Test-Path $runTranscriptJson) { $runTranscriptJson } else { $baseTranscriptJson }
            tournament_transcript_md = if (Test-Path $runTranscriptMd) { $runTranscriptMd } else { $baseTranscriptMd }
        }
    }

    $summary | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $summaryOut

    "[$(Get-Date -Format o)] Completed successfully." | Tee-Object -FilePath $runLog -Append
    Write-Host "Done. Log: $runLog"
    Write-Host "Judge variance JSON: $testOut"
    Write-Host "Summary JSON: $summaryOut"
}
finally {
    if (-not $KeepContainer) {
        "[$(Get-Date -Format o)] Stopping container $containerName" | Tee-Object -FilePath $runLog -Append
        try { & docker stop $containerName | Out-Null } catch {}
    } else {
        "[$(Get-Date -Format o)] Keeping container $containerName running" | Tee-Object -FilePath $runLog -Append
    }
}
