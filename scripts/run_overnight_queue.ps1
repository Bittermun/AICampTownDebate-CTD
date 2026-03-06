# Overnight Experiment Queue
# Run: .\scripts\run_overnight_queue.ps1

param(
    [int]$LocalRuns   = 10,
    [int]$DirectRuns  = 8,
    [int]$Concurrency = 2,
    [string]$GroqKey  = $env:OPENAI_COMPAT_API_KEY
)

$TS     = (Get-Date).ToString("yyyyMMddTHHmmssZ")
$Root   = "logs/overnight_$TS"
$Python = "C:\Python314\python.exe"

New-Item -ItemType Directory -Force -Path $Root | Out-Null
Write-Host "OVERNIGHT QUEUE started: $TS"
Write-Host "Output root: $Root"

function Run-Lane {
    param([string]$label, [string]$config, [int]$runs, [string]$outDir)
    Write-Host ""
    Write-Host "--- LANE: $label ($runs runs) ---"
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    $t = [System.Diagnostics.Stopwatch]::StartNew()
    & $Python scripts/run_tournament_batch.py `
        --config $config `
        --runs $runs `
        --output-root $outDir `
        --batch-id "${label}_${TS}" `
        --concurrency $Concurrency `
        --no-gate-judge-variance `
        --no-gate-judge-calibration
    $t.Stop()
    $m = [math]::Round($t.Elapsed.TotalMinutes, 1)
    Write-Host "DONE: $label in $m min"
    return $m
}

$t1 = Run-Lane "1_rookie"  "configs/rookie_baseline.yaml"         $LocalRuns  "$Root/1_rookie"
$t2 = Run-Lane "2_veteran" "configs/veteran_emergent.yaml"        $LocalRuns  "$Root/2_veteran"
$t3 = Run-Lane "3_direct"  "configs/veteran_vs_rookie_direct.yaml" $DirectRuns "$Root/3_direct"

Write-Host ""
Write-Host "--- LANE: 4_evolution (pop=4, gen=2) ---"
New-Item -ItemType Directory -Force -Path "$Root/4_evolution" | Out-Null
$t4sw = [System.Diagnostics.Stopwatch]::StartNew()
& $Python scripts/run_evolution_campaign.py `
    --tournament-config "configs/veteran_emergent.yaml" `
    --model-id "qwen2.5:7b" `
    --population-size 4 `
    --generations 2 `
    --elite-count 2 `
    --output-dir "$Root/4_evolution" `
    --allow-stub `
    --disable-judge-variance-gate `
    --disable-judge-calibration-gate
$t4sw.Stop()
$t4 = [math]::Round($t4sw.Elapsed.TotalMinutes, 1)
Write-Host "DONE: 4_evolution in $t4 min"

if ($GroqKey) {
    $env:OPENAI_COMPAT_BASE_URL = "https://api.groq.com/openai/v1"
    $env:OPENAI_COMPAT_API_KEY  = $GroqKey
    $t5 = Run-Lane "5_groq_judge" "configs/veteran_groq_judge.yaml" 6 "$Root/5_groq_judge"
} else {
    Write-Host "SKIP lane 5: no Groq key"
    $t5 = 0
}

$total = $t1 + $t2 + $t3 + $t4 + $t5
Write-Host ""
Write-Host "ALL DONE. Total: $total min"
Write-Host "Results: $Root"
Write-Host ""
Write-Host "Compare:"
Write-Host "  python scripts/compare_batch_results.py $Root/1_rookie $Root/2_veteran --label-a Rookie --label-b Veteran"
Write-Host "  python scripts/compare_batch_results.py $Root/1_rookie $Root/3_direct  --label-a Rookie --label-b Direct"
