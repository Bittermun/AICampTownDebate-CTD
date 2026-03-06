param(
    [string]$TranscriptPath = "",
    [int]$RoundId = 1,
    [int]$Port = 8787,
    [double]$Speed = 1.0
)

$ErrorActionPreference = "Stop"

if (-not $TranscriptPath) {
    $latest = Get-ChildItem -Path "logs" -Filter "*_transcript.json" -Recurse -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($latest) {
        $TranscriptPath = $latest.FullName
    } else {
        $TranscriptPath = "logs/tournament_results_transcript.json"
    }
}

Write-Host "Launching round stream viewer..."
Write-Host "Transcript: $TranscriptPath"
Write-Host "Round: $RoundId | Port: $Port | Speed: $Speed x"

python scripts/round_stream_viewer.py `
    --transcript "$TranscriptPath" `
    --round-id $RoundId `
    --port $Port `
    --speed $Speed `
    --open-browser
