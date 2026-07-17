#!/usr/bin/env bash
# fundamental-analysis-skill installer (macOS / Linux)
#
# Zero-flag, auto-detects everything.
#
#   curl -fsSL https://raw.githubusercontent.com/Alexey-Rivkin/fundamental-analysis-skill/main/install.sh | bash
#
# The installer:
#   1. Checks for git (required; errors out if missing).
#   2. Checks for uv; installs it if missing (Homebrew on macOS if available,
#      else the official astral.sh installer).
#   3. Detects which agents are set up — Claude Code (~/.claude or `claude`
#      binary) and Codex CLI (~/.codex or `codex` binary) — and installs the
#      skill for each. If none is detected, installs into ~/.claude by default.
#   4. Updates existing installs in place instead of re-cloning.

set -euo pipefail

REPO="https://github.com/Alexey-Rivkin/fundamental-analysis-skill.git"
BRANCH="main"
SKILL_NAME="fundamental-analysis"

# --- Helpers --------------------------------------------------------------

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33mWARN:\033[0m %s\n' "$*"; }
fatal() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

has() { command -v "$1" >/dev/null 2>&1; }

install_uv() {
    if [ "$(uname -s)" = "Darwin" ] && has brew; then
        info "Installing uv via Homebrew"
        brew install uv
        return
    fi
    if has curl; then
        info "Installing uv via astral.sh (curl)"
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif has wget; then
        info "Installing uv via astral.sh (wget)"
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        fatal "Neither brew, curl, nor wget is available. Install uv manually then re-run:
       https://docs.astral.sh/uv/getting-started/installation/"
    fi
    # Astral installer drops uv into ~/.local/bin (or ~/.cargo/bin on older versions)
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
}

install_to() {
    local dest="$1"
    if [ -d "$dest/.git" ]; then
        info "Updating existing install at $dest"
        git -C "$dest" fetch --depth 1 origin "$BRANCH" >/dev/null
        git -C "$dest" reset --hard "origin/$BRANCH" >/dev/null
    else
        [ -e "$dest" ] && fatal "$dest already exists and is not a git checkout. Move it aside and re-run."
        mkdir -p "$(dirname "$dest")"
        info "Cloning $REPO -> $dest"
        git clone --quiet --depth 1 --branch "$BRANCH" "$REPO" "$dest"
    fi
}

# --- Preflight ------------------------------------------------------------

has git || fatal "git is not on PATH. Install Git first, then re-run."

if has uv; then
    info "uv found: $(uv --version)"
else
    install_uv
    has uv || warn "uv install ran but uv is still not on PATH — open a new shell to pick it up."
fi

# --- Detect installed agents ---------------------------------------------

claude_detected=0
codex_detected=0

if has claude || [ -d "$HOME/.claude" ]; then
    claude_detected=1
fi
if has codex || [ -d "$HOME/.codex" ]; then
    codex_detected=1
fi

if [ "$claude_detected" -eq 0 ] && [ "$codex_detected" -eq 0 ]; then
    info "No agent (Claude Code / Codex CLI) detected — defaulting to Claude Code location."
    claude_detected=1
fi

# --- Install to each detected agent --------------------------------------

installed_paths=()

if [ "$claude_detected" -eq 1 ]; then
    dest="$HOME/.claude/skills/$SKILL_NAME"
    install_to "$dest"
    installed_paths+=("$dest|claude")
fi

if [ "$codex_detected" -eq 1 ]; then
    dest="$HOME/.codex/skills/$SKILL_NAME"
    install_to "$dest"
    installed_paths+=("$dest|codex")
fi

# --- Report --------------------------------------------------------------

echo
info "Done."
for entry in "${installed_paths[@]}"; do
    path="${entry%|*}"
    kind="${entry##*|}"
    echo "  ✓ $path"
    case "$kind" in
        claude)
            echo "    Claude Code picks this up automatically on the next session."
            ;;
        codex)
            echo "    Codex CLI: add to your project's AGENTS.md:"
            echo "      When the user asks to analyze a stock ticker,"
            echo "      follow the instructions in $path/SKILL.md"
            ;;
    esac
done
echo
echo "Try it:"
echo "  In Claude Code / Codex, ask:  analyze NVDA"
echo "  Standalone: uv run --with yfinance python ${installed_paths[0]%|*}/scripts/analyze.py NVDA --peers auto"
