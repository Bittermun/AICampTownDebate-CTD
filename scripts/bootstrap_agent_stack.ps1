param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }),
    [string]$Ref = "main",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[bootstrap] $Message"
}

function Invoke-SkillInstall {
    param(
        [string]$InstallerScript,
        [string]$Repo,
        [string]$Path,
        [string]$RefName,
        [string]$DestinationRoot,
        [switch]$DryRun
    )

    $skillName = Split-Path $Path -Leaf
    $dest = Join-Path $DestinationRoot $skillName
    if (Test-Path $dest) {
        Write-Step "skip $skillName (already installed)"
        return
    }

    $cmd = "python `"$InstallerScript`" --repo $Repo --path $Path --ref $RefName"
    if ($DryRun) {
        Write-Step "dry-run: $cmd"
        return
    }

    Write-Step "installing $skillName from $Repo/$Path@$RefName"
    & python $InstallerScript --repo $Repo --path $Path --ref $RefName
    if ($LASTEXITCODE -ne 0) {
        throw "Skill installation failed for $skillName"
    }
}

function Set-ReadGithubWindowsPatch {
    param(
        [string]$CodexHomePath,
        [switch]$DryRun
    )

    $runningOnWindows = $false
    if (Get-Variable -Name IsWindows -ErrorAction SilentlyContinue) {
        $runningOnWindows = [bool]$IsWindows
    } elseif ($env:OS -eq "Windows_NT") {
        $runningOnWindows = $true
    }

    if (-not $runningOnWindows) {
        Write-Step "read-github patch not needed on non-Windows hosts"
        return
    }

    $target = Join-Path $CodexHomePath "skills\read-github\scripts\gitmcp.py"
    if (-not (Test-Path $target)) {
        Write-Step "read-github not installed yet; patch skipped"
        return
    }

    $content = Get-Content -Raw -Path $target
    if ($content -match "_npx_command\(\)") {
        Write-Step "read-github windows patch already present"
        return
    }

    $updated = $content -replace '(from typing import Optional\s*)', "`$1`r`n`r`ndef _npx_command() -> str:`r`n    # Windows commonly exposes npx as npx.cmd, which subprocess may not resolve from `"npx`".`r`n    return `"npx.cmd`" if sys.platform.startswith(`"win`") else `"npx`"`r`n"
    $updated = $updated -replace '\["npx", "-y", "mcp-remote", mcp_url\]', '[_npx_command(), "-y", "mcp-remote", mcp_url]'

    if ($DryRun) {
        Write-Step "dry-run: patch read-github for Windows npx.cmd compatibility"
        return
    }

    Set-Content -Path $target -Value $updated -Encoding UTF8
    Write-Step "applied read-github Windows compatibility patch"
}

$installer = Join-Path $CodexHome "skills\.system\skill-installer\scripts\install-skill-from-github.py"
if (-not (Test-Path $installer)) {
    throw "Could not find installer script at: $installer"
}

$skillRoot = Join-Path $CodexHome "skills"
if (-not (Test-Path $skillRoot)) {
    throw "Could not find skill destination root at: $skillRoot"
}

$skillSpecs = @(
    @{ Repo = "openai/skills"; Path = "skills/.curated/openai-docs" },
    @{ Repo = "openai/skills"; Path = "skills/.curated/jupyter-notebook" },
    @{ Repo = "openai/skills"; Path = "skills/.curated/spreadsheet" },
    @{ Repo = "openai/skills"; Path = "skills/.curated/pdf" },
    @{ Repo = "openai/skills"; Path = "skills/.curated/doc" },
    @{ Repo = "openai/skills"; Path = "skills/.curated/security-threat-model" },
    @{ Repo = "Orchestra-Research/AI-Research-SKILLs"; Path = "11-evaluation/lm-evaluation-harness" },
    @{ Repo = "Orchestra-Research/AI-Research-SKILLs"; Path = "12-inference-serving/vllm" },
    @{ Repo = "Orchestra-Research/AI-Research-SKILLs"; Path = "13-mlops/mlflow" },
    @{ Repo = "Orchestra-Research/AI-Research-SKILLs"; Path = "13-mlops/weights-and-biases" },
    @{ Repo = "Orchestra-Research/AI-Research-SKILLs"; Path = "17-observability/phoenix" },
    @{ Repo = "am-will/codex-skills"; Path = "skills/context7" },
    @{ Repo = "am-will/codex-skills"; Path = "skills/read-github" }
)

Write-Step "starting skill bootstrap into $skillRoot"
foreach ($spec in $skillSpecs) {
    Invoke-SkillInstall -InstallerScript $installer -Repo $spec.Repo -Path $spec.Path -RefName $Ref -DestinationRoot $skillRoot -DryRun:$DryRun
}

Set-ReadGithubWindowsPatch -CodexHomePath $CodexHome -DryRun:$DryRun

Write-Step "done"
Write-Host "Restart Codex to pick up new skills."
