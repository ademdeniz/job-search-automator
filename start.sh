#!/bin/bash
# Job Search Automator — startup script with preflight checks

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
YEL='\033[1;33m'
GRN='\033[0;32m'
NC='\033[0m'

ok()   { echo -e "${GRN}✔${NC}  $1"; }
warn() { echo -e "${YEL}⚠${NC}  $1"; }
fail() { echo -e "${RED}✘${NC}  $1"; }

echo ""
echo "🎯 Job Search Automator — preflight check"
echo "──────────────────────────────────────────"

ERRORS=0

# ── Python ────────────────────────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1)
    ok "Python found: $PY_VER"
else
    fail "python3 not found. Install Python 3.9+ from https://python.org"
    ERRORS=$((ERRORS + 1))
fi

# ── Dependencies ──────────────────────────────────────────────────────────────
if python3 -c "import streamlit, anthropic, playwright, docx, pandas" 2>/dev/null; then
    ok "Python dependencies installed"
else
    warn "Some dependencies are missing. Installing from requirements.txt…"
    pip3 install -r requirements.txt
    if [ $? -eq 0 ]; then
        ok "Dependencies installed successfully"
    else
        fail "Dependency install failed. Run: pip3 install -r requirements.txt"
        ERRORS=$((ERRORS + 1))
    fi
fi

# ── Playwright / Chromium ─────────────────────────────────────────────────────
if python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
    # Check if Chromium browser is actually installed
    if python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    b.close()
" 2>/dev/null; then
        ok "Playwright + Chromium ready"
    else
        warn "Playwright installed but Chromium browser not found. Installing…"
        python3 -m playwright install chromium
        if [ $? -eq 0 ]; then
            ok "Chromium installed"
        else
            fail "Chromium install failed. Run: python3 -m playwright install chromium"
            ERRORS=$((ERRORS + 1))
        fi
    fi
else
    fail "Playwright not installed. Run: pip3 install playwright && python3 -m playwright install chromium"
    ERRORS=$((ERRORS + 1))
fi

# ── Anthropic API key ─────────────────────────────────────────────────────────
if [ -n "$ANTHROPIC_API_KEY" ]; then
    ok "ANTHROPIC_API_KEY found in environment"
else
    # Try loading from ~/.zshrc or ~/.bashrc
    for rc in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile"; do
        if [ -f "$rc" ]; then
            KEY=$(grep 'ANTHROPIC_API_KEY' "$rc" | head -1 | sed "s/.*=//;s/'//g;s/\"//g" | xargs)
            if [ -n "$KEY" ]; then
                export ANTHROPIC_API_KEY="$KEY"
                ok "ANTHROPIC_API_KEY loaded from $rc"
                break
            fi
        fi
    done
    if [ -z "$ANTHROPIC_API_KEY" ]; then
        warn "ANTHROPIC_API_KEY not set — scoring and tailoring will not work."
        warn "Get a key at https://console.anthropic.com and add it to ~/.zshrc:"
        warn "  export ANTHROPIC_API_KEY=sk-ant-..."
    fi
fi

# ── Profile ───────────────────────────────────────────────────────────────────
if [ -f "$SCRIPT_DIR/profile.json" ]; then
    ok "profile.json found"
else
    warn "No profile.json found — you'll need to fill in your profile on first launch."
    warn "Go to the 👤 Profile page and save your resume and contact info."
fi

# ── Database init ─────────────────────────────────────────────────────────────
python3 -c "
import sys; sys.path.insert(0, '.')
from storage.database import init_db
init_db()
" 2>/dev/null && ok "Database ready" || warn "Database init had warnings (non-fatal)"

echo "──────────────────────────────────────────"

if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}Preflight failed with $ERRORS error(s). Fix the issues above before continuing.${NC}"
    exit 1
fi

echo -e "${GRN}All checks passed. Launching UI…${NC}"
echo ""

# ── background scheduler ──────────────────────────────────────────────────────
python3 "$SCRIPT_DIR/scheduler.py" &
SCHEDULER_PID=$!
echo -e "${GRN}✔${NC}  Scheduler started (PID $SCHEDULER_PID)"

# Kill scheduler when Streamlit exits
trap "kill $SCHEDULER_PID 2>/dev/null" EXIT

python3 -m streamlit run "$SCRIPT_DIR/ui.py"
