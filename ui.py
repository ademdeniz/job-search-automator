# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
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
    get_unscored_jobs, get_jobs_without_description, stats, get_applied_jobs,
    delete_job,
)
from storage.profile import load_profile, save_profile

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
SOURCES = ["linkedin", "indeed", "remoteok", "weworkremotely", "dice", "greenhouse", "lever", "himalayas", "jobspresso"]
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
    t1.metric("Applied", _ap.get("applied", 0))
    t2.metric("Interview", _ap.get("interviewing", 0))
    t3.metric("Offer", _ap.get("offer", 0))
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
        filter_status = st.selectbox("Status", ["New only", "All"] + VALID_STATUSES)
    with col3:
        filter_source = st.selectbox("Source", ["All"] + SOURCES)
    with col4:
        min_score = st.slider("Min Score", 0, 100, 0, step=5)
    with col5:
        remote_only = st.checkbox("Remote only")

    sort_by = st.radio("Sort by", ["Score ↓", "Date ↓"], horizontal=True)

    # ── load data ─────────────────────────────────────────────────────────────
    # "New only" = default view — hides applied/interviewing/offer (those live in My Applications)
    if filter_status == "New only":
        status_filter = "new"
    elif filter_status == "All":
        status_filter = None
    else:
        status_filter = filter_status

    jobs = get_all_jobs(
        status=status_filter,
        source=None if filter_source == "All" else filter_source,
        keyword=keyword or None,
        remote=True if remote_only else None,
    )

    if min_score > 0:
        jobs = [j for j in jobs if (j.get("score") or 0) >= min_score]

    if sort_by == "Score ↓":
        jobs.sort(key=lambda j: (j.get("score") or -1), reverse=True)

    st.caption(f"{len(jobs)} job(s) found — applied jobs are in 📁 My Applications")

    if not jobs:
        st.info("No new jobs found. Scrape more from the Actions tab — your applied jobs are safe in 📁 My Applications.")
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

                    # Detect aggregators — show company override field
                    AGGREGATORS = {
                        "remotehunter", "jobgether", "indeed", "linkedin",
                        "glassdoor", "ziprecruiter", "simplyhired", "scoutit",
                    }
                    is_aggregator = job.get("company", "").lower().strip() in AGGREGATORS
                    company_override_key = f"company_override_{job['id']}"

                    if is_aggregator:
                        st.warning(f"⚠️ Listed via **{job['company']}** — enter the real company name below.")
                        st.text_input(
                            "Real company name",
                            key=company_override_key,
                            placeholder="e.g. Veracyte",
                        )

                    if not has_desc:
                        st.caption("No description — paste one below to enable tailoring.")
                        manual_desc = st.text_area(
                            "Paste job description",
                            key=manual_key,
                            height=160,
                            placeholder="Copy the full job description from the job board and paste it here…",
                        )
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
                        # Save description to DB if it came from the text area
                        if not has_desc and tailor_desc:
                            from storage.database import update_description
                            update_description(job["id"], tailor_desc)

                        # If user provided a real company name, temporarily patch the job
                        # by prepending it to the description so Claude sees it
                        override = st.session_state.get(company_override_key, "").strip()
                        if override:
                            run_cli(["main.py", "tailor", str(job["id"]), "--company", override])
                            spinner_company = override
                        else:
                            spinner_company = job["company"]

                        with st.spinner("Claude is tailoring your resume… (30–60 sec)"):
                            out = run_cli(["main.py", "tailor", str(job["id"])]
                                         + (["--company", override] if override else []))

                        # Parse file paths and real company from CLI output
                        import re as _re
                        resume_match  = _re.search(r"Resume:\s+(.+\.docx)", out)
                        cl_match      = _re.search(r"Cover letter:\s+(.+\.docx)", out)
                        company_match = _re.search(r"Real company identified:\s+(.+?)\s+\(was:", out)
                        real_company  = company_match.group(1).strip() if company_match else job["company"]
                        key = f"tailor_files_{job['id']}"
                        st.session_state[key] = {
                            "resume": resume_match.group(1).strip() if resume_match else None,
                            "cover_letter": cl_match.group(1).strip() if cl_match else None,
                            "company": real_company,
                            "log": out,
                        }

                    # ── Show downloads from session state (persists across rerenders) ──
                    state_key = f"tailor_files_{job['id']}"
                    if state_key in st.session_state:
                        files = st.session_state[state_key]
                        if files.get("log"):
                            st.code(files["log"])

                        # ── ATS check badge ───────────────────────────────
                        log = files.get("log", "")
                        if "[ATS] ✅" in log:
                            st.success("ATS Check: Resume passed")
                        elif "[ATS] ⚠️" in log:
                            # Extract issue lines from the log
                            issues = [
                                line.strip().lstrip("•").strip()
                                for line in log.splitlines()
                                if line.strip().startswith("•")
                            ]
                            st.warning(
                                "ATS Check: Issues found\n"
                                + ("\n".join(f"• {i}" for i in issues) if issues else "")
                            )

                        dl_col1, dl_col2 = st.columns(2)
                        co = files.get("company", job["company"]).replace(" ", "_")
                        if files.get("resume") and os.path.exists(files["resume"]):
                            with open(files["resume"], "rb") as f:
                                dl_col1.download_button(
                                    "⬇ Resume.docx",
                                    data=f.read(),
                                    file_name=f"resume_{co}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"dl_resume_{job['id']}",
                                )
                        if files.get("cover_letter") and os.path.exists(files["cover_letter"]):
                            with open(files["cover_letter"], "rb") as f:
                                dl_col2.download_button(
                                    "⬇ Cover Letter.docx",
                                    data=f.read(),
                                    file_name=f"cover_letter_{co}.docx",
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
            _default_kw = load_profile().get("target_role", "") or "QA engineer SDET test automation"
            if "scrape_keywords" not in st.session_state:
                st.session_state["scrape_keywords"] = _default_kw
            keywords_input = st.text_input(
                "Keywords",
                key="scrape_keywords",
                help="Space-separated keywords — set your default in the Profile page.",
            )
            location_mode = st.radio(
                "Location mode",
                ["🇺🇸 US Remote only", "🌐 World Remote", "📍 Local / Hybrid", "🔀 Both (US Remote + Local)"],
                index=0,
                help=(
                    "US Remote: remote jobs limited to United States.\n"
                    "World Remote: remote jobs worldwide (no country filter).\n"
                    "Local / Hybrid: LinkedIn + Indeed near your specified location.\n"
                    "Both: US Remote + local in sequence."
                ),
            )
            local_location = ""
            if location_mode in ("📍 Local / Hybrid", "🔀 Both (US Remote + Local)"):
                local_location = st.text_input(
                    "Location (city, state or zip code)",
                    value="Erie, PA",
                    placeholder="e.g. Pittsburgh, PA  or  16509",
                )
        with s_col2:
            sources_input = st.multiselect(
                "Sources  (LinkedIn & Indeed first)",
                SOURCES,
                default=["linkedin", "indeed", "remoteok", "weworkremotely", "greenhouse", "lever", "himalayas", "jobspresso"],
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
            "🗑️ Fresh search — clear new/rejected jobs first",
            value=False,
            help="Removes jobs with status 'new' or 'rejected' before scraping. "
                 "Applied, interviewing, and offer records are always preserved.",
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
                if location_mode in ("🇺🇸 US Remote only", "🌐 World Remote", "🔀 Both (US Remote + Local)"):
                    remote_location = "Remote US" if location_mode in ("🇺🇸 US Remote only", "🔀 Both (US Remote + Local)") else "Remote"
                    label = "US remote" if remote_location == "Remote US" else "worldwide remote"
                    with st.spinner(f"Scraping {label} jobs…"):
                        out = run_cli(
                            ["main.py", "scrape"]
                            + kw_args
                            + ["--location", remote_location]
                            + src_args_remote
                            + max_args
                            + days_args
                        )
                    output_lines.append(f"── Remote pass ({label}) ──\n" + out)

                # ── Local / hybrid pass ───────────────────────────────────
                if location_mode in ("📍 Local / Hybrid", "🔀 Both (US Remote + Local)"):
                    local_sources = [s for s in ERIE_SOURCES if s in sources_input]
                    if not local_location.strip():
                        output_lines.append("⚠️ Local pass skipped — enter a location above.")
                    elif local_sources:
                        with st.spinner(f"Scraping local / hybrid jobs near {local_location}…"):
                            out = run_cli(
                                ["main.py", "scrape"]
                                + kw_args
                                + ["--location", local_location.strip()]
                                + ["--sources"] + local_sources
                                + max_args
                                + days_args
                            )
                        output_lines.append(f"── Local pass ({local_location.strip()}) ──\n" + out)
                    else:
                        output_lines.append("⚠️ Local pass skipped — LinkedIn and/or Indeed must be selected.")

                st.code("\n\n".join(output_lines))

                # ── post-scrape summary ───────────────────────────────────
                new_jobs = get_all_jobs(status="new")
                st.success(
                    f"Done! Found **{len(new_jobs)} new job(s)** in the database. "
                    f"Go to **📋 Job Board** to review and start applying."
                )
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


# ════════════════════════════════════════════════════════════════════════════
# PAGE: MY APPLICATIONS
# ════════════════════════════════════════════════════════════════════════════
elif page == "📁 My Applications":
    st.title("📁 My Applications")
    st.caption("Your application history — preserved across fresh searches.")

    PIPELINE = ["applied", "interviewing", "offer"]
    PIPELINE_COLOR = {
        "applied":      "#3b82f6",
        "interviewing": "#a855f7",
        "offer":        "#22c55e",
    }
    NEXT_STAGE = {
        "applied":      "interviewing",
        "interviewing": "offer",
    }
    NEXT_LABEL = {
        "applied":      "→ Interviewing",
        "interviewing": "→ Offer",
    }

    # ── filters ───────────────────────────────────────────────────────────────
    f1, f2, f3 = st.columns([2, 1.5, 1.5])
    with f1:
        app_keyword = st.text_input("🔍 Search", placeholder="title, company…", key="app_kw")
    with f2:
        app_status = st.selectbox("Stage", ["All"] + PIPELINE, key="app_status")
    with f3:
        app_sort = st.radio("Sort by", ["Date applied ↓", "Score ↓"], horizontal=True, key="app_sort")

    # Load — only active pipeline applications (no rejected — those are deleted)
    app_jobs = get_all_jobs(
        status=None if app_status == "All" else app_status,
        keyword=app_keyword or None,
    )
    app_jobs = [j for j in app_jobs if j["status"] in PIPELINE]

    if app_sort == "Score ↓":
        app_jobs.sort(key=lambda j: (j.get("score") or -1), reverse=True)

    # ── pipeline summary bar ──────────────────────────────────────────────────
    db_stats = stats()
    _ap = db_stats["by_status"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Applied",      _ap.get("applied", 0))
    m2.metric("Interviewing", _ap.get("interviewing", 0))
    m3.metric("Offer",        _ap.get("offer", 0))
    st.divider()

    if not app_jobs:
        st.info("No applications yet. Mark jobs as 'applied' from the Job Board to track them here.")
        st.stop()

    st.caption(f"{len(app_jobs)} application(s)")

    # ── application cards ─────────────────────────────────────────────────────
    for job in app_jobs:
        score      = job.get("score")
        level      = match_level(score)
        s_color    = SCORE_COLOR.get(level, "#94a3b8")
        st_color   = PIPELINE_COLOR.get(job["status"], "#94a3b8")

        with st.container():
            st.markdown(
                f"""
                <div style="border-left: 4px solid {st_color}; padding: 12px 16px;
                            background: #1e293b; border-radius: 6px; margin-bottom: 4px;">
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
                            <span style="background:{s_color}22; color:{s_color};
                                         padding:2px 10px; border-radius:99px; font-size:0.8rem;">
                                {score_badge(score)}
                            </span>
                            <span style="background:{st_color}22; color:{st_color};
                                         padding:2px 10px; border-radius:99px; font-size:0.8rem;
                                         font-weight:600;">
                                {job['status']}
                            </span>
                            <span style="color:#64748b; font-size:0.8rem;">{job['source']}</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # ── inline action buttons ─────────────────────────────────────────
            btn_cols = st.columns([1, 1, 1, 4])
            next_stage = NEXT_STAGE.get(job["status"])
            if next_stage:
                if btn_cols[0].button(
                    NEXT_LABEL[job["status"]],
                    key=f"advance_{job['id']}",
                    use_container_width=True,
                ):
                    update_status(job["id"], next_stage)
                    st.rerun()
            if btn_cols[1].button(
                "🗑 Remove",
                key=f"delete_{job['id']}",
                use_container_width=True,
            ):
                delete_job(job["id"])
                st.rerun()

            with st.expander(f"Details — ID {job['id']}", expanded=False):
                d1, d2 = st.columns([2, 1])
                with d1:
                    if job.get("score_reason"):
                        st.markdown(f"**AI Analysis:** {job['score_reason']}")
                    desc = job.get("description") or "No description saved."
                    st.markdown(f"**Description:**\n\n{desc[:1000]}{'…' if len(desc) > 1000 else ''}")
                with d2:
                    st.markdown(f"**Salary:** {job.get('salary') or 'N/A'}")
                    st.markdown(f"**Posted:** {job.get('posted_date') or 'N/A'}")
                    st.markdown(f"**Remote:** {'Yes' if job.get('remote') else 'No'}")
                    if job.get("url"):
                        st.link_button("🔗 Open Job", job["url"])

                    st.divider()
                    # Stage corrector — lets you fix mistakes / go back
                    correct_stage = st.selectbox(
                        "Correct stage",
                        PIPELINE,
                        index=PIPELINE.index(job["status"]) if job["status"] in PIPELINE else 0,
                        key=f"correct_{job['id']}",
                    )
                    if correct_stage != job["status"]:
                        if st.button("Save", key=f"correctsave_{job['id']}"):
                            update_status(job["id"], correct_stage)
                            st.rerun()

                    # Notes field stored in session state (lightweight, no DB change needed)
                    notes_key = f"notes_{job['id']}"
                    st.text_area(
                        "Notes (interview prep, contacts, follow-up dates…)",
                        key=notes_key,
                        height=100,
                        placeholder="e.g. Phone screen with Sarah on Apr 10, asked about Appium experience…",
                    )


# ════════════════════════════════════════════════════════════════════════════
# PAGE: PROFILE
# ════════════════════════════════════════════════════════════════════════════
elif page == "👤 Profile":
    st.title("👤 Profile")
    st.caption("Your info is used for resume tailoring and cover letter generation.")

    profile = load_profile()

    st.subheader("Contact Info")
    c1, c2 = st.columns(2)
    with c1:
        p_name        = st.text_input("Full name",    value=profile.get("name", ""))
        p_email       = st.text_input("Email",         value=profile.get("email", ""))
        p_location    = st.text_input("Location",     value=profile.get("location", ""),
                                      placeholder="e.g. Erie, PA")
        p_target_role = st.text_input(
            "Target role / keywords",
            value=profile.get("target_role", ""),
            placeholder="e.g. SDET test automation Appium",
            help="Used as the default search keywords when scraping jobs.",
        )
    with c2:
        p_linkedin = st.text_input("LinkedIn URL", value=profile.get("linkedin", ""),
                                   placeholder="linkedin.com/in/your-handle")
        p_github   = st.text_input("GitHub URL",   value=profile.get("github", ""),
                                   placeholder="github.com/yourhandle")
        p_website  = st.text_input("Website / Portfolio", value=profile.get("website", ""),
                                   placeholder="yourportfolio.com (optional)")

    st.divider()
    st.subheader("Resume")
    st.caption("Paste your full resume as plain text. This is what Claude uses for tailoring.")
    p_resume = st.text_area(
        "Resume text",
        value=profile.get("resume", ""),
        height=500,
        label_visibility="collapsed",
        placeholder="Paste your resume here…",
    )

    st.divider()
    if st.button("💾 Save Profile", type="primary"):
        save_profile({
            "name":        p_name.strip(),
            "email":       p_email.strip(),
            "linkedin":    p_linkedin.strip(),
            "github":      p_github.strip(),
            "website":     p_website.strip(),
            "location":    p_location.strip(),
            "target_role": p_target_role.strip(),
            "resume":      p_resume.strip(),
        })
        st.toast("Profile saved!", icon="✅")
