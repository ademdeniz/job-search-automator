# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
import re as _re
import csv
import io
import streamlit as st
from storage.database import get_all_jobs, get_unscored_jobs, get_jobs_without_description
from storage.profile import load_profile
from pages.utils import VALID_STATUSES, SOURCES, ERIE_SOURCES, run_cli, show_cli_result


def render():
    st.title("🔧 Actions")
    st.caption("Run scraping, scoring, and fetching operations directly from the UI.")

    # ── post-scrape result banner (persists after rerun) ──────────────────────
    if "last_scrape_count" in st.session_state:
        count = st.session_state["last_scrape_count"]
        st.success(
            f"Done! Found **{count} new job(s)** in the database. "
            f"Go to **📋 Job Board** to review and start applying."
        )
        if st.button("Dismiss", key="dismiss_scrape_banner"):
            del st.session_state["last_scrape_count"]
            st.rerun()

    # ── scrape ────────────────────────────────────────────────────────────────
    with st.expander("🕷️ Scrape Jobs", expanded=True):
        st.markdown("Search job boards and pull new listings into the database.")

        s_col1, s_col2 = st.columns(2)
        with s_col1:
            _default_kw = load_profile().get("target_role", "") or ""
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

                if fresh_search:
                    with st.spinner("Clearing database…"):
                        out, _ = run_cli(["main.py", "clear"])
                    output_lines.append(out)

                _kw_tokens = [t for t in _re.split(r"[\s|&,]+", keywords_input) if t.strip()]
                kw_args      = ["--keywords"] + _kw_tokens
                src_args_remote = ["--sources"] + sources_input
                max_args     = ["--max-results", str(max_results)]
                days_args    = ["--days-ago", str(days_ago)] if days_ago else []

                scrape_errors = []

                if location_mode in ("🇺🇸 US Remote only", "🌐 World Remote", "🔀 Both (US Remote + Local)"):
                    remote_location = "Remote US" if location_mode in ("🇺🇸 US Remote only", "🔀 Both (US Remote + Local)") else "Remote"
                    label = "US remote" if remote_location == "Remote US" else "worldwide remote"
                    with st.spinner(f"Scraping {label} jobs…"):
                        out, ok = run_cli(
                            ["main.py", "scrape"]
                            + kw_args
                            + ["--location", remote_location]
                            + src_args_remote
                            + max_args
                            + days_args
                        )
                    output_lines.append(f"── Remote pass ({label}) ──\n" + out)
                    if not ok:
                        scrape_errors.append(f"Remote scrape failed: {out[:200]}")

                if location_mode in ("📍 Local / Hybrid", "🔀 Both (US Remote + Local)"):
                    local_sources = [s for s in ERIE_SOURCES if s in sources_input]
                    if not local_location.strip():
                        output_lines.append("⚠️ Local pass skipped — enter a location above.")
                    elif local_sources:
                        with st.spinner(f"Scraping local / hybrid jobs near {local_location}…"):
                            out, ok = run_cli(
                                ["main.py", "scrape"]
                                + kw_args
                                + ["--location", local_location.strip()]
                                + ["--sources"] + local_sources
                                + max_args
                                + days_args
                            )
                        output_lines.append(f"── Local pass ({local_location.strip()}) ──\n" + out)
                        if not ok:
                            scrape_errors.append(f"Local scrape failed: {out[:200]}")
                    else:
                        output_lines.append("⚠️ Local pass skipped — LinkedIn and/or Indeed must be selected.")

                if scrape_errors:
                    st.error("Scraping encountered errors:\n\n" + "\n\n".join(scrape_errors))
                st.code("\n\n".join(output_lines))

                new_jobs = get_all_jobs(status="new")
                st.session_state["last_scrape_count"] = len(new_jobs)
                st.rerun()

    # ── fetch descriptions ────────────────────────────────────────────────────
    with st.expander("📄 Fetch Full Descriptions"):
        st.markdown("Visit each job page and extract the full description so jobs can be scored. Supports **LinkedIn, Indeed, and Dice**.")
        from scrapers.linkedin import _SUPPORTED_SOURCES
        no_desc_all = [j for j in get_jobs_without_description() if j.get("source") in _SUPPORTED_SOURCES]
        by_source = {}
        for j in no_desc_all:
            by_source[j["source"]] = by_source.get(j["source"], 0) + 1
        summary = ", ".join(f"{s}: {n}" for s, n in by_source.items()) if by_source else "none"
        st.info(f"{len(no_desc_all)} job(s) missing descriptions — {summary}")
        if st.button("▶ Fetch Descriptions"):
            with st.spinner(f"Fetching {len(no_desc_all)} descriptions via headless browser… (this takes a few minutes)"):
                out, ok = run_cli(["main.py", "fetch"])
            show_cli_result(out, ok)
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
                out, ok = run_cli(args)
            st.session_state["last_score_output"] = (out, ok)
            st.rerun()

    if "last_score_output" in st.session_state:
        _s_out, _s_ok = st.session_state["last_score_output"]
        show_cli_result(_s_out, _s_ok)
        if st.button("Dismiss", key="dismiss_score_output"):
            del st.session_state["last_score_output"]
            st.rerun()

    # ── export ────────────────────────────────────────────────────────────────
    with st.expander("📤 Export to CSV"):
        exp_status = st.selectbox("Filter by status", ["All"] + VALID_STATUSES, key="exp_status")
        if st.button("⬇ Export CSV"):
            jobs = get_all_jobs(status=None if exp_status == "All" else exp_status)
            if jobs:
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
