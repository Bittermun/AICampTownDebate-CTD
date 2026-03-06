# Veteran vs Rookie Comparison Launcher
# Runs two parallel batches: one with rookie configs, one with veteran configs.
# Uses the SAME topics/judge/model so results are directly comparable.
# Hypothesis: Veterans (EV guard + Kelly + evolutionary directives) outperform Rookies
# (concise-prompted, no economic reasoning, no memory).

param(
    [int]$Runs = 6,
    [int]$Concurrency = 2
)

$TS = (Get-Date).ToString("yyyyMMddTHHmmssZ")

Write-Host "============================================"
Write-Host " VETERAN vs ROOKIE BENCHMARK"
Write-Host " Runs: $Runs per lane | Concurrency: $Concurrency"
Write-Host " Timestamp: $TS"
Write-Host "============================================"

# --- Lane A: ROOKIE ---
$rookieOut = "logs/comparison_$TS/rookie"
Write-Host "[launcher] Starting ROOKIE lane -> $rookieOut"
$rookieProc = Start-Process python -ArgumentList @(
    "scripts/run_tournament_batch.py",
    "--config", "configs/rookie_baseline.yaml",
    "--runs", "$Runs",
    "--output-root", $rookieOut,
    "--batch-id", "rookie_$TS",
    "--concurrency", "$Concurrency",
    "--no-gate-judge-variance",
    "--no-gate-judge-calibration"
) -WorkingDirectory (Get-Location).Path -WindowStyle Normal -PassThru

# --- Lane B: VETERAN ---
$veteranOut = "logs/comparison_$TS/veteran"
Write-Host "[launcher] Starting VETERAN lane -> $veteranOut"
$veteranProc = Start-Process python -ArgumentList @(
    "scripts/run_tournament_batch.py",
    "--config", "configs/veteran_emergent.yaml",
    "--runs", "$Runs",
    "--output-root", $veteranOut,
    "--batch-id", "veteran_$TS",
    "--concurrency", "$Concurrency",
    "--no-gate-judge-variance",
    "--no-gate-judge-calibration"
) -WorkingDirectory (Get-Location).Path -WindowStyle Normal -PassThru

Write-Host ""
Write-Host "[launcher] Both lanes running:"
Write-Host "  Rookie  PID=$($rookieProc.Id)  -> $rookieOut"
Write-Host "  Veteran PID=$($veteranProc.Id) -> $veteranOut"
Write-Host ""
Write-Host "When complete, compare results with:"
Write-Host "  python scripts/compare_batch_results.py $rookieOut $veteranOut"
