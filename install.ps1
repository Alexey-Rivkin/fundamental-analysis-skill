# fundamental-analysis-skill installer (Windows / PowerShell)
#
# Zero-flag, auto-detects everything.
#
#   irm https://raw.githubusercontent.com/Alexey-Rivkin/fundamental-analysis-skill/main/install.ps1 | iex
#
# The installer:
#   1. Checks for git (required; errors out if missing).
#   2. Checks for uv; installs it if missing (official astral.sh installer).
#   3. Detects which agents are set up — Claude Code (%USERPROFILE%\.claude or
#      `claude` binary) and Codex CLI (%USERPROFILE%\.codex or `codex` binary)
#      — and installs the skill for each. If none is detected, installs into
#      %USERPROFILE%\.claude by default.
#   4. Updates existing installs in place instead of re-cloning.

$ErrorActionPreference = "Stop"
$Repo   = "https://github.com/Alexey-Rivkin/fundamental-analysis-skill.git"
$Branch = "main"
$SkillName = "fundamental-analysis"

function Test-Cmd($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function Info($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Warn($msg) { Write-Host "WARN: $msg" -ForegroundColor Yellow }
function Fatal($msg) { Write-Error $msg; exit 1 }

function Install-Uv {
    Info "Installing uv via astral.sh"
    powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $localBin = Join-Path $env:USERPROFILE ".local\bin"
    if (Test-Path $localBin) { $env:Path = "$localBin;$env:Path" }
}

function Install-To($dest) {
    if (Test-Path (Join-Path $dest ".git")) {
        Info "Updating existing install at $dest"
        git -C $dest fetch --depth 1 origin $Branch | Out-Null
        git -C $dest reset --hard "origin/$Branch" | Out-Null
    }
    else {
        if (Test-Path $dest) {
            Fatal "$dest already exists and is not a git checkout. Move it aside and re-run."
        }
        $parent = Split-Path -Parent $dest
        New-Item -ItemType Directory -Force -Path $parent | Out-Null
        Info "Cloning $Repo -> $dest"
        git clone --quiet --depth 1 --branch $Branch $Repo $dest
    }
}

# --- Preflight ------------------------------------------------------------

if (-not (Test-Cmd git)) {
    Fatal "git is not on PATH. Install Git for Windows first (https://git-scm.com/download/win), then re-run."
}

if (Test-Cmd uv) {
    Info "uv found: $(uv --version)"
} else {
    Install-Uv
    if (-not (Test-Cmd uv)) {
        Warn "uv install ran but uv is still not on PATH — open a new PowerShell window to pick it up."
    }
}

# --- Detect installed agents ---------------------------------------------

$claudeDetected = $false
$codexDetected  = $false

if ((Test-Cmd claude) -or (Test-Path (Join-Path $env:USERPROFILE ".claude"))) {
    $claudeDetected = $true
}
if ((Test-Cmd codex) -or (Test-Path (Join-Path $env:USERPROFILE ".codex"))) {
    $codexDetected = $true
}

if (-not $claudeDetected -and -not $codexDetected) {
    Info "No agent (Claude Code / Codex CLI) detected — defaulting to Claude Code location."
    $claudeDetected = $true
}

# --- Install to each detected agent --------------------------------------

$installed = @()

if ($claudeDetected) {
    $dest = Join-Path $env:USERPROFILE ".claude\skills\$SkillName"
    Install-To $dest
    $installed += @{ Path = $dest; Kind = "claude" }
}
if ($codexDetected) {
    $dest = Join-Path $env:USERPROFILE ".codex\skills\$SkillName"
    Install-To $dest
    $installed += @{ Path = $dest; Kind = "codex" }
}

# --- Report --------------------------------------------------------------

Write-Host ""
Info "Done."
foreach ($e in $installed) {
    Write-Host "  ✓ $($e.Path)"
    switch ($e.Kind) {
        "claude" {
            Write-Host "    Claude Code picks this up automatically on the next session."
        }
        "codex" {
            Write-Host "    Codex CLI: add to your project's AGENTS.md:"
            Write-Host "      When the user asks to analyze a stock ticker,"
            Write-Host "      follow the instructions in $($e.Path)\SKILL.md"
        }
    }
}
Write-Host ""
Write-Host "Try it:"
Write-Host "  In Claude Code / Codex, ask:  analyze NVDA"
Write-Host "  Standalone: uv run --with yfinance python $($installed[0].Path)\scripts\analyze.py NVDA --peers auto"
