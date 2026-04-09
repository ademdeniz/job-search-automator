# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
"""
Job Search Automator — Streamlit UI entry point.

Run with:
    streamlit run ui.py
"""

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from storage.database import stats
from storage.profile import load_profile
from pages import job_board, dashboard, actions, my_applications, profile as profile_page

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Job Search Automator",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎯 Job Search")
    st.caption("Powered by Claude AI")
    st.divider()

    page = st.radio(
        "Navigate",
        ["👤 Profile", "🔧 Actions", "📋 Job Board", "📊 Dashboard", "📁 My Applications"],
        label_visibility="collapsed",
    )

    st.divider()
    db_stats = stats()
    st.metric("Total Jobs", db_stats["total"])
    col1, col2 = st.columns(2)
    col1.metric("Scored", db_stats.get("scored", 0))
    col2.metric("Avg Score", f"{db_stats.get('avg_score', 0):.0f}")

    st.divider()
    st.caption("🗂️ Application Tracker")
    _ap = db_stats["by_status"]
    t1, t2, t3 = st.columns(3)
    t1.metric("Applied",   _ap.get("applied", 0))
    t2.metric("Interview", _ap.get("interviewing", 0))
    t3.metric("Offer",     _ap.get("offer", 0))
    if _ap.get("applied", 0) + _ap.get("interviewing", 0) + _ap.get("offer", 0) > 0:
        st.caption("✅ Preserved on fresh search")

# ── profile completeness check ────────────────────────────────────────────────
_profile = load_profile()
_profile_complete = bool(_profile.get("name") and _profile.get("resume"))
if not _profile_complete and page != "👤 Profile":
    st.warning(
        "**Complete your profile first.** "
        "Go to **👤 Profile** in the sidebar to add your name, contact info, and resume. "
        "Scoring and tailoring won't work without it."
    )

# ── routing ───────────────────────────────────────────────────────────────────
if page == "👤 Profile":
    profile_page.render()
elif page == "🔧 Actions":
    actions.render()
elif page == "📋 Job Board":
    job_board.render()
elif page == "📊 Dashboard":
    dashboard.render()
elif page == "📁 My Applications":
    my_applications.render()
