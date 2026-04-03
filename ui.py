"""
Job Search Automator — Streamlit UI

Run with:
    streamlit run ui.py
"""

import os
import sys
import sqlite3
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd

# ── path so imports work from the repo root ──────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from storage.database import (
    get_all_jobs, get_job_by_id, update_status, save_score,
    get_unscored_jobs, get_jobs_without_description, stats,
)

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Job Search Automator",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── color helpers ─────────────────────────────────────────────────────────────
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
# LinkedIn + Indeed first — best location-aware sources
SOURCES = ["linkedin", "indeed", "remoteok", "weworkremotely", "dice", "greenhouse", "lever"]
ERIE_SOURCES = ["linkedin", "indeed"]   # only these support geographic location well


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


def run_cli(cmd: list[str]) -> str:
    env = os.environ.copy()
    # Load API key from ~/.zshrc if not already in environment
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
    result = subprocess.run(
        [sys.executable] + cmd,
        capture_output=True, text=True,
        cwd=os.path.dirname(__file__),
        env=env,
    )
    return (result.stdout + result.stderr).strip()


# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🎯 Job Search")
    st.caption("Powered by Claude AI")
    st.divider()

    page = st.radio(
        "Navigate",
        ["📋 Job Board", "📊 Dashboard", "🔧 Actions"],
        label_visibility="collapsed",
    )

    st.divider()
    db_stats = stats()
    st.metric("Total Jobs", db_stats["total"])
    col1, col2 = st.columns(2)
    col1.metric("Scored", db_stats.get("scored", 0))
    col2.metric("Avg Score", f"{db_stats.get('avg_score', 0):.0f}")


# ════════════════════════════════════════════════════════════════════════════
# PAGE: JOB BOARD
# ════════════════════════════════════════════════════════════════════════════
if page == "📋 Job Board":
    st.title("📋 Job Board")

    # ── filters ──────────────────────────────────────────────────────────────
    col1, col2, col3, col4, col5 = st.columns([2, 1.5, 1.5, 1.5, 1])

    with col1:
        keyword = st.text_input("🔍 Search", placeholder="title, company, description…")
    with col2:
        filter_status = st.selectbox("Status", ["All"] + VALID_STATUSES)
    with col3:
        filter_source = st.selectbox("Source", ["All"] + SOURCES)
    with col4:
        min_score = st.slider("Min Score", 0, 100, 0, step=5)
    with col5:
        remote_only = st.checkbox("Remote only")

    sort_by = st.radio("Sort by", ["Score ↓", "Date ↓"], horizontal=True)

    # ── load data ─────────────────────────────────────────────────────────────
    jobs = get_all_jobs(
        status=None if filter_status == "All" else filter_status,
        source=None if filter_source == "All" else filter_source,
        keyword=keyword or None,
        remote=True if remote_only else None,
    )

    if min_score > 0:
        jobs = [j for j in jobs if (j.get("score") or 0) >= min_score]

    if sort_by == "Score ↓":
        jobs.sort(key=lambda j: (j.get("score") or -1), reverse=True)

    st.caption(f"{len(jobs)} job(s) found")

    if not jobs:
        st.info("No jobs match your filters. Try scraping more jobs from the Actions tab.")
        st.stop()

    # ── job cards ─────────────────────────────────────────────────────────────
    for job in jobs:
        score = job.get("score")
        level = match_level(score)
        border_color = SCORE_COLOR.get(level, "#94a3b8")
        status_color = STATUS_COLOR.get(job["status"], "#94a3b8")

        with st.container():
            st.markdown(
                f"""
                <div style="border-left: 4px solid {border_color}; padding: 12px 16px;
                            background: #1e293b; border-radius: 6px; margin-bottom: 8px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="font-size:1.05rem; font-weight:600; color:#f1f5f9;">
                                {job['title']}
                            </span>
                            &nbsp;
                            <span style="color:#94a3b8; font-size:0.9rem;">
                                {job['company']} · {job['location']}
                            </span>
                        </div>
                        <div style="display:flex; gap:8px; align-items:center;">
                            <span style="background:{border_color}22; color:{border_color};
                                         padding:2px 10px; border-radius:99px; font-size:0.8rem;">
                                {score_badge(score)}
                            </span>
                            <span style="background:{status_color}22; color:{status_color};
                                         padding:2px 10px; border-radius:99px; font-size:0.8rem;">
                                {job['status']}
                            </span>
                            <span style="color:#64748b; font-size:0.8rem;">
                                {job['source']}
                            </span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.expander(f"Details — ID {job['id']}", expanded=False):
                c1, c2 = st.columns([2, 1])
                with c1:
                    if job.get("score_reason"):
                        st.markdown(f"**AI Analysis:** {job['score_reason']}")
                    desc = (job.get("description") or "No description available.")
                    st.markdown(f"**Description:**\n\n{desc[:1500]}{'…' if len(desc) > 1500 else ''}")
                with c2:
                    st.markdown(f"**Salary:** {job.get('salary') or 'N/A'}")
                    st.markdown(f"**Type:** {job.get('job_type') or 'N/A'}")
                    st.markdown(f"**Posted:** {job.get('posted_date') or 'N/A'}")
                    st.markdown(f"**Remote:** {'Yes' if job.get('remote') else 'No'}")
                    if job.get("url"):
                        st.link_button("🔗 Open Job", job["url"])

                    new_status = st.selectbox(
                        "Update status",
                        VALID_STATUSES,
                        index=VALID_STATUSES.index(job["status"]),
                        key=f"status_{job['id']}",
                    )
                    if new_status != job["status"]:
                        if st.button("Save", key=f"save_{job['id']}"):
                            update_status(job["id"], new_status)
                            st.success(f"Status updated to **{new_status}**")
                            st.rerun()

                    st.divider()

                    # ── Tailor resume + cover letter ──────────────────────
                    has_desc = bool(job.get("description"))
                    manual_key = f"manual_desc_{job['id']}"

                    if not has_desc:
                        st.caption("No description — paste one below to enable tailoring.")
                        manual_desc = st.text_area(
                            "Paste job description",
                            key=manual_key,
                            height=160,
                            placeholder="Copy the full job description from the job board and paste it here…",
                        )
                        # Save it to DB so future actions use it too
                        if manual_desc and st.button("💾 Save description", key=f"save_desc_{job['id']}"):
                            from storage.database import update_description
                            update_description(job["id"], manual_desc)
                            st.success("Description saved.")
                            st.rerun()
                    else:
                        manual_desc = ""

                    tailor_desc = job.get("description") or st.session_state.get(manual_key, "")
                    can_tailor  = bool(tailor_desc.strip())

                    if st.button(
                        "✍️ Tailor Resume + Cover Letter",
                        key=f"tailor_{job['id']}",
                        disabled=not can_tailor,
                        type="primary",
                    ):
                        # If description came from the text area (not yet in DB),
                        # temporarily save it so the CLI subprocess can read it.
                        if not has_desc and tailor_desc:
                            from storage.database import update_description
                            update_description(job["id"], tailor_desc)

                        with st.spinner(f"Claude is tailoring your resume for {job['company']}… (30–60 sec)"):
                            out = run_cli(["main.py", "tailor", str(job["id"])])
                        st.code(out)

                        # Show download buttons if files were created
                        import re as _re
                        resume_match = _re.search(r"Resume:\s+(.+\.docx)", out)
                        cl_match     = _re.search(r"Cover letter:\s+(.+\.docx)", out)
                        if resume_match and os.path.exists(resume_match.group(1)):
                            with open(resume_match.group(1), "rb") as f:
                                st.download_button(
                                    "⬇ Download Resume.docx",
                                    data=f.read(),
                                    file_name=f"resume_{job['company'].replace(' ', '_')}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"dl_resume_{job['id']}",
                                )
                        if cl_match and os.path.exists(cl_match.group(1)):
                            with open(cl_match.group(1), "rb") as f:
                                st.download_button(
                                    "⬇ Download Cover Letter.docx",
                                    data=f.read(),
                                    file_name=f"cover_letter_{job['company'].replace(' ', '_')}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"dl_cl_{job['id']}",
                                )


# ════════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ════════════════════════════════════════════════════════════════════════════
elif page == "📊 Dashboard":
    st.title("📊 Dashboard")

    db_stats = stats()
    total = db_stats["total"]

    # ── top metrics ───────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Jobs", total)
    m2.metric("Scored", db_stats.get("scored", 0))
    m3.metric("Avg Match", f"{db_stats.get('avg_score', 0):.1f}/100")
    applied = db_stats["by_status"].get("applied", 0)
    m4.metric("Applied", applied)
    interviewing = db_stats["by_status"].get("interviewing", 0)
    m5.metric("Interviewing", interviewing)

    st.divider()

    col1, col2 = st.columns(2)

    # ── score distribution ────────────────────────────────────────────────────
    with col1:
        st.subheader("Score Distribution")
        jobs = get_all_jobs()
        scored = [j for j in jobs if j.get("score") is not None]
        if scored:
            df = pd.DataFrame(scored)
            bins = [0, 20, 40, 60, 70, 80, 90, 101]
            labels = ["0-20", "21-40", "41-60", "61-70", "71-80", "81-90", "91-100"]
            df["range"] = pd.cut(df["score"], bins=bins, labels=labels, right=False)
            chart_data = df["range"].value_counts().sort_index().reset_index()
            chart_data.columns = ["Score Range", "Count"]
            st.bar_chart(chart_data.set_index("Score Range"))
        else:
            st.info("No scored jobs yet. Run `score` from the Actions tab.")

    # ── jobs by source ────────────────────────────────────────────────────────
    with col2:
        st.subheader("Jobs by Source")
        if db_stats["by_source"]:
            src_df = pd.DataFrame(
                list(db_stats["by_source"].items()),
                columns=["Source", "Count"]
            ).set_index("Source")
            st.bar_chart(src_df)

    st.divider()

    col3, col4 = st.columns(2)

    # ── pipeline funnel ───────────────────────────────────────────────────────
    with col3:
        st.subheader("Application Pipeline")
        pipeline_order = ["new", "applied", "interviewing", "offer", "rejected"]
        pipeline_data = {s: db_stats["by_status"].get(s, 0) for s in pipeline_order}
        pipe_df = pd.DataFrame(
            list(pipeline_data.items()), columns=["Stage", "Count"]
        ).set_index("Stage")
        st.bar_chart(pipe_df)

    # ── top matches table ─────────────────────────────────────────────────────
    with col4:
        st.subheader("Top Matches")
        top_jobs = sorted(
            [j for j in get_all_jobs() if j.get("score") is not None],
            key=lambda j: j["score"], reverse=True
        )[:10]
        if top_jobs:
            rows = []
            for j in top_jobs:
                rows.append({
                    "Score": j["score"],
                    "Title": j["title"][:35],
                    "Company": j["company"][:20],
                    "Source": j["source"],
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════════════════════
# PAGE: ACTIONS
# ════════════════════════════════════════════════════════════════════════════
elif page == "🔧 Actions":
    st.title("🔧 Actions")
    st.caption("Run scraping, scoring, and fetching operations directly from the UI.")

    # ── scrape ────────────────────────────────────────────────────────────────
    with st.expander("🕷️ Scrape Jobs", expanded=True):
        st.markdown("Search job boards and pull new listings into the database.")

        s_col1, s_col2 = st.columns(2)
        with s_col1:
            keywords_input = st.text_input(
                "Keywords",
                value="QA engineer SDET quality assurance test automation",
                help="Space-separated keywords",
            )
            location_mode = st.radio(
                "Location mode",
                ["🌐 Remote only", "📍 Erie PA (local / hybrid)", "🔀 Both"],
                index=0,
                help=(
                    "Remote: searches all selected sources for remote jobs.\n"
                    "Erie PA: searches LinkedIn + Indeed for on-site / hybrid roles near Erie, PA.\n"
                    "Both: does both passes in sequence."
                ),
            )
        with s_col2:
            sources_input = st.multiselect(
                "Sources  (LinkedIn & Indeed first)",
                SOURCES,
                default=["linkedin", "indeed", "remoteok", "weworkremotely", "greenhouse", "lever"],
            )
            max_results = st.slider("Max results per source", 10, 100, 50, step=10)
            freshness = st.select_slider(
                "Posted within",
                options=["Any time", "7 days", "3 days", "24 hours"],
                value="7 days",
            )
            days_ago_map = {"Any time": None, "7 days": 7, "3 days": 3, "24 hours": 1}
            days_ago = days_ago_map[freshness]

        fresh_search = st.checkbox(
            "🗑️ Fresh search — clear all existing jobs first",
            value=False,
            help="Deletes everything in the database before scraping so you start clean.",
        )

        if st.button("▶ Run Scrape", type="primary"):
            if not sources_input:
                st.warning("Select at least one source.")
            else:
                output_lines = []

                # ── optional clear ────────────────────────────────────────
                if fresh_search:
                    with st.spinner("Clearing database…"):
                        out = run_cli(["main.py", "clear"])
                    output_lines.append(out)

                kw_args = ["--keywords"] + keywords_input.split()
                src_args_remote = ["--sources"] + sources_input
                src_args_erie   = ["--sources"] + [s for s in ERIE_SOURCES if s in sources_input]
                max_args = ["--max-results", str(max_results)]
                days_args = ["--days-ago", str(days_ago)] if days_ago else []

                # ── remote pass ───────────────────────────────────────────
                if location_mode in ("🌐 Remote only", "🔀 Both"):
                    with st.spinner("Scraping remote jobs…"):
                        out = run_cli(
                            ["main.py", "scrape"]
                            + kw_args
                            + ["--location", "Remote"]
                            + src_args_remote
                            + max_args
                            + days_args
                        )
                    output_lines.append("── Remote pass ──\n" + out)

                # ── Erie PA pass ──────────────────────────────────────────
                if location_mode in ("📍 Erie PA (local / hybrid)", "🔀 Both"):
                    erie_sources = [s for s in ERIE_SOURCES if s in sources_input]
                    if erie_sources:
                        with st.spinner("Scraping Erie PA local / hybrid jobs (LinkedIn + Indeed)…"):
                            out = run_cli(
                                ["main.py", "scrape"]
                                + kw_args
                                + ["--location", "Erie, PA"]
                                + src_args_erie
                                + max_args
                                + days_args
                            )
                        output_lines.append("── Erie PA pass ──\n" + out)
                    else:
                        output_lines.append("⚠️ Erie PA pass skipped — LinkedIn and/or Indeed must be selected.")

                st.code("\n\n".join(output_lines))
                st.rerun()

    # ── fetch descriptions ────────────────────────────────────────────────────
    with st.expander("📄 Fetch Descriptions (LinkedIn)"):
        st.markdown("Visit each LinkedIn job page and extract the full description so jobs can be scored.")
        no_desc = get_jobs_without_description(source="linkedin")
        st.info(f"{len(no_desc)} LinkedIn job(s) missing descriptions.")
        if st.button("▶ Fetch Descriptions"):
            with st.spinner(f"Fetching {len(no_desc)} descriptions via headless browser… (this takes ~2 min)"):
                out = run_cli(["main.py", "fetch", "--source", "linkedin"])
            st.code(out)
            st.rerun()

    # ── score ─────────────────────────────────────────────────────────────────
    with st.expander("🤖 Score Jobs with AI"):
        st.markdown("Claude AI scores every job against your resume and returns a 0–100 match score.")
        unscored = get_unscored_jobs()
        st.info(f"{len(unscored)} job(s) ready to score.")
        rescore_all = st.checkbox("Re-score all jobs (including already scored)")
        if st.button("▶ Score Jobs", type="primary"):
            args = ["main.py", "score"]
            if rescore_all:
                args.append("--all")
            with st.spinner("Scoring with Claude AI… (a few seconds per job)"):
                out = run_cli(args)
            st.code(out)
            st.rerun()

    # ── export ────────────────────────────────────────────────────────────────
    with st.expander("📤 Export to CSV"):
        exp_status = st.selectbox("Filter by status", ["All"] + VALID_STATUSES, key="exp_status")
        if st.button("⬇ Export CSV"):
            jobs = get_all_jobs(status=None if exp_status == "All" else exp_status)
            if jobs:
                import csv, io
                fields = ["id", "score", "title", "company", "location", "remote",
                          "source", "status", "salary", "job_type", "posted_date", "url", "score_reason"]
                buf = io.StringIO()
                writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                for job in jobs:
                    job["remote"] = "yes" if job.get("remote") == 1 else "no"
                    writer.writerow(job)
                st.download_button(
                    "💾 Download jobs.csv",
                    data=buf.getvalue(),
                    file_name="jobs.csv",
                    mime="text/csv",
                )
            else:
                st.warning("No jobs to export.")
