param(
    [string]$Config = "configs/ollama_tournament_recommended.yaml",
    [switch]$GateJudgeVariance = $true
)

$ErrorActionPreference = "Stop"

$gateArg = ""
if ($GateJudgeVariance) { $gateArg = "--gate-judge-variance" }

python demo_tournament.py --config $Config $gateArg
