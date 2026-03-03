param(
    [string]$Config = "configs/benchmark_phase1.yaml",
    [string]$TournamentConfig = "configs/tournament_config.yaml",
    [string]$ModelId = "stub",
    [string]$JudgeModel = "stub",
    [int]$Seed = 101,
    [string]$FixturesDir = "benchmarks/fixtures",
    [ValidateSet("default", "core_live_stretch_fixture", "all_live", "all_fixture")]
    [string]$SourceMode = "all_fixture",
    [string]$ArtifactRoot = "logs/smoke_e2e",
    [string]$RunLabel = "smoke_e2e",
    [bool]$AllowStub = $true,
    [switch]$EnableModelDerivedMetrics,
    [int]$NumRoundsOverride = 1,
    [int]$MaxIterationsOverride = 1,
    [ValidateSet("tier_a", "tier_b", "tier_c")]
    [string]$MinTier = "tier_b",
    [string]$IncludeTiers = "",
    [string]$Notes = "Smoke pipeline dataset prep"
)

$ErrorActionPreference = "Stop"

$cmd = @(
    "scripts/run_e2e_smoke_pipeline.py",
    "--config", $Config,
    "--tournament-config", $TournamentConfig,
    "--model-id", $ModelId,
    "--judge-model", $JudgeModel,
    "--seed", "$Seed",
    "--fixtures-dir", $FixturesDir,
    "--source-mode", $SourceMode,
    "--artifact-root", $ArtifactRoot,
    "--run-label", $RunLabel,
    "--num-rounds-override", "$NumRoundsOverride",
    "--max-iterations-override", "$MaxIterationsOverride",
    "--min-tier", $MinTier,
    "--notes", $Notes
)

if ($AllowStub) {
    $cmd += "--allow-stub"
} else {
    $cmd += "--no-allow-stub"
}

if ($EnableModelDerivedMetrics) {
    $cmd += "--enable-model-derived-metrics"
}

if ($IncludeTiers) {
    $cmd += @("--include-tiers", $IncludeTiers)
}

python @cmd
if ($LASTEXITCODE -ne 0) {
    throw "run_e2e_smoke_pipeline failed with exit code $LASTEXITCODE"
}
