# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
"""Shared helpers, constants, and utilities used across all UI pages."""

import os
import re
import sys
import subprocess
from datetime import datetime, timedelta

import streamlit as st

# ── constants ─────────────────────────────────────────────────────────────────
SCORE_COLOR = {
    "excellent": "#22c55e",
    "good":      "#84cc16",
    "fair":      "#f59e0b",
    "poor":      "#ef4444",
    None:        "#94a3b8",
}

STATUS_COLOR = {
    "new":          "#94a3b8",
    "applied":      "#3b82f6",
    "interviewing": "#a855f7",
    "offer":        "#22c55e",
    "rejected":     "#ef4444",
}

VALID_STATUSES = ["new", "applied", "interviewing", "offer", "rejected"]
PIPELINE       = ["applied", "interviewing", "offer"]
PIPELINE_COLOR = {
    "applied":      "#3b82f6",
    "interviewing": "#a855f7",
    "offer":        "#22c55e",
}

# LinkedIn + Indeed first — best location-aware sources
SOURCES      = ["linkedin", "indeed", "remoteok", "weworkremotely", "dice", "greenhouse", "lever", "himalayas", "jobspresso"]
ERIE_SOURCES = ["linkedin", "indeed"]


# ── score helpers ─────────────────────────────────────────────────────────────
def match_level(score):
    if score is None:
        return None
    if score >= 90: return "excellent"
    if score >= 70: return "good"
    if score >= 50: return "fair"
    return "poor"


def score_badge(score):
    if score is None:
        return "⬜ Not scored"
    level = match_level(score)
    colors = {"excellent": "🟢", "good": "🟡", "fair": "🟠", "poor": "🔴"}
    return f"{colors[level]} {score}/100"


# ── date formatting ───────────────────────────────────────────────────────────
def fmt_date(raw: str) -> str:
    """Parse various date formats and return a clean 'Apr 07, 2026' string."""
    if not raw:
        return "N/A"
    from email.utils import parsedate_to_datetime
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw[:19], fmt).strftime("%b %d, %Y")
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(raw).strftime("%b %d, %Y")
    except Exception:
        pass
    return raw[:10] if len(raw) >= 10 else raw


# ── metadata extraction ───────────────────────────────────────────────────────
def extract_metadata(text: str) -> dict:
    """Extract posted_date, salary, job_type from pasted job description text."""
    result = {}
    t = text.lower()

    if re.search(r'\bfull[- ]time\b', t):
        result["job_type"] = "full-time"
    elif re.search(r'\bpart[- ]time\b', t):
        result["job_type"] = "part-time"
    elif re.search(r'\bcontract\b', t):
        result["job_type"] = "contract"

    today = datetime.now()
    if re.search(r'posted\s+(just\s+now|today)', t):
        result["posted_date"] = today.strftime("%Y-%m-%d")
    else:
        m = re.search(r'posted\s+(\d+)\s+day', t)
        if m:
            result["posted_date"] = (today - timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")
        else:
            m = re.search(r'posted\s+(\d+)\s+hour', t)
            if m:
                result["posted_date"] = today.strftime("%Y-%m-%d")

    def _parse_num(s):
        s = s.replace(",", "")
        if s.lower().endswith("k"):
            return int(s[:-1]) * 1000
        return int(s)

    for pattern in [
        r'(?:USD\s*)?\$([\d,]+[kK]?)\s*[-–]\s*(?:USD\s*)?\$([\d,]+[kK]?)',
        r'([\d,]{6,})\s*[-–]\s*([\d,]{6,})',
    ]:
        m = re.search(pattern, text)
        if m:
            try:
                lo, hi = _parse_num(m.group(1)), _parse_num(m.group(2))
                if hi >= lo and ((lo > 10000 and hi > 10000) or (lo < 500 and hi < 500)):
                    result["salary"] = f"${m.group(1)} - ${m.group(2)}"
                    break
            except (ValueError, AttributeError):
                pass
    if not result.get("salary"):
        m = re.search(r'(?:salary|compensation)[:\s]+(?:USD\s*)?\$?([\d,]+[kK]?)', text, re.IGNORECASE)
        if m:
            result["salary"] = f"${m.group(1)}"

    return result


# ── CLI runner ────────────────────────────────────────────────────────────────
def run_cli(cmd: list) -> tuple:
    """Run a CLI command. Returns (output, success)."""
    env = os.environ.copy()
    if not env.get("ANTHROPIC_API_KEY"):
        try:
            with open(os.path.expanduser("~/.zshrc")) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("export ANTHROPIC_API_KEY="):
                        env["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip().strip("'\"")
                        break
        except Exception:
            pass
    try:
        result = subprocess.run(
            [sys.executable] + cmd,
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(__file__)),
            env=env,
            timeout=600,
        )
        out = (result.stdout + result.stderr).strip()
        _error_signals = ["Traceback (most recent call last)", "Error code:", "credit balance",
                          "FileNotFoundError", "ModuleNotFoundError"]
        failed = result.returncode != 0 or any(s in out for s in _error_signals)
        return out, not failed
    except subprocess.TimeoutExpired:
        return "Operation timed out after 10 minutes.", False
    except Exception as e:
        return f"Failed to run command: {e}", False


def show_cli_result(out: str, success: bool):
    """Display CLI output — error box if failed, code block if success."""
    if not success:
        st.error(f"Something went wrong:\n\n```\n{out}\n```")
    elif out:
        st.code(out)


# ── PDF conversion via LibreOffice ───────────────────────────────────────────
def docx_to_pdf(docx_path: str):
    """
    Convert a .docx file to PDF using LibreOffice headless.
    Returns the PDF path on success, None if LibreOffice is not installed or conversion fails.
    """
    import shutil
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    out_dir = os.path.dirname(docx_path)
    try:
        result = subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, docx_path],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            return None
        pdf_path = os.path.splitext(docx_path)[0] + ".pdf"
        return pdf_path if os.path.exists(pdf_path) else None
    except Exception:
        return None


def has_libreoffice() -> bool:
    """Return True if LibreOffice is available for PDF conversion."""
    import shutil
    return bool(shutil.which("soffice") or shutil.which("libreoffice"))


# ── direct Claude call ────────────────────────────────────────────────────────
def claude_call(system: str, user: str, model: str = "claude-haiku-4-5-20251001", max_tokens: int = 2048) -> str:
    """Make a direct Claude API call. Returns response text or raises."""
    import anthropic as _anthropic
    if not os.environ.get("ANTHROPIC_API_KEY"):
        try:
            with open(os.path.expanduser("~/.zshrc")) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("export ANTHROPIC_API_KEY="):
                        os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip().strip("'\"")
                        break
        except Exception:
            pass
    client = _anthropic.Anthropic()
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text.strip()
