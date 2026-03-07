# Multi-key Groq campaign launcher
# concurrency=1 per account to stay under 6K TPM free-tier rate limit.
param(
    [int]$RunsPerKey = 50,
    [int]$Concurrency = 1,
    [string]$Config = "configs/groq_emergent_config.yaml"
)

# ---- ADD YOUR GROQ API KEYS HERE ----
$GroqKeys = @(
    "YOUR_API_KEY_HERE"  # account 1
)
# -------------------------------------

$Timestamp = (Get-Date).ToString("yyyyMMddTHHmmssZ")
$Jobs = @()

foreach ($i in 0..($GroqKeys.Count - 1)) {
    $key = $GroqKeys[$i]
    $acct = $i + 1
    $outDir = "logs/groq_multikey_$Timestamp/account_$acct"
    $startSeed = 101 + ($i * $RunsPerKey)

    Write-Host "[launcher] Starting account $acct -> $outDir (start-seed=$startSeed)"

    $proc = Start-Process powershell -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
        "`$env:OPENAI_COMPAT_BASE_URL='https://api.groq.com/openai/v1'; " +
        "`$env:OPENAI_COMPAT_API_KEY='$key'; " +
        "C:\Python314\python.exe scripts/run_tournament_batch.py " +
        "--config $Config --runs $RunsPerKey --output-root `"$outDir`" " +
        "--start-seed $startSeed " +
        "--concurrency $Concurrency --no-gate-judge-variance --no-gate-judge-calibration"
    ) -WorkingDirectory (Get-Location).Path -WindowStyle Normal -PassThru

    $Jobs += [pscustomobject]@{ Acct = $acct; Pid = $proc.Id; StartSeed = $startSeed; OutDir = $outDir }
}

Write-Host ""
Write-Host "[launcher] $($Jobs.Count) campaign(s) started:"
$Jobs | Format-Table Acct, Pid, StartSeed, OutDir -AutoSize
Write-Host "Stop all: $($Jobs | ForEach-Object { "Stop-Process -Id $($_.Pid) -Force" } | Join-String -Separator '; ')"
