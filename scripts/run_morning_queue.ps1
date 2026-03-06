# Morning Campaign Queue Master Orchestrator
# Runs 3 lanes sequentially.
# Lane 1 (Scarcity vs Abundance) is run via the Groq Multi-key launcher.
# Lanes 2 & 3 (Cross-model, Kelly sweep) are run locally on the Nvidia GPU.

$Timestamp = (Get-Date).ToString("yyyyMMdd_HHmmss")
$LogDir = "logs/morning_queue_$Timestamp"
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

Write-Host "========================================================"
Write-Host "   AI Camp Town Debate - Morning Campaign Queue"
Write-Host "========================================================"
Write-Host "Starting at $Timestamp"
Write-Host "Queue plan:"
Write-Host "  1. Scarcity vs Abundance (Groq: Llama-3.3-70B)"
Write-Host "  2. Cross-Model (Local: Qwen2.5 vs Llama3.1)"
Write-Host "  3. Kelly Sweep (Local: Aggressive vs Conservative)"
Write-Host "========================================================"

Write-Host "`n[1/3] Launching Groq Scarcity vs Abundance (Lane 1)..."
# Using 50 runs, 1 concurrency to stay under Groq free tier limits.
# Make sure your API key is set in scripts/launch_groq_multikey.ps1!
.\scripts\launch_groq_multikey.ps1 -RunsPerKey 50 -Concurrency 1 -Config "configs/morning_scarcity_groq.yaml"
# Note: launch_groq_multikey uses Start-Process, so it launches asynchronously in the background.

Write-Host "`n[2/3] Waiting 10 seconds, then launching Local runs (Lanes 2 & 3)..."
Start-Sleep -Seconds 10

# Lane 2
Write-Host "`n---> Starting Lane 2: Cross-Model (Qwen2.5 vs Llama3.1)..."
$Lane2Dir = "$LogDir/lane2_cross_model"
C:\Python314\python.exe scripts/run_tournament_batch.py `
    --config configs/morning_cross_model.yaml `
    --runs 20 --concurrency 2 --output-root $Lane2Dir

# Lane 3
Write-Host "`n---> Starting Lane 3: Kelly Sweep (Aggressive vs Conservative)..."
$Lane3Dir = "$LogDir/lane3_kelly_sweep"
C:\Python314\python.exe scripts/run_tournament_batch.py `
    --config configs/morning_kelly_sweep.yaml `
    --runs 20 --concurrency 2 --output-root $Lane3Dir

Write-Host "`n========================================================"
Write-Host "Morning Queue Local Processes Completed!"
Write-Host "Your Groq background process may still be running. Check the Groq taskbar window."
Write-Host "========================================================"
