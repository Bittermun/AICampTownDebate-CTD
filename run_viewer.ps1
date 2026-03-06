param(
    [int]$RoundId = 1
)

$scriptPath = Join-Path $PSScriptRoot "scripts/run_round_stream_viewer.ps1"
& $scriptPath -RoundId $RoundId
