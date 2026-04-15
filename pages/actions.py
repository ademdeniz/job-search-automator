# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
import re as _re
import csv
import io
import os
import streamlit as st
from storage.database import get_all_jobs, get_unscored_jobs, get_jobs_without_description
from storage.profile import load_profile, save_profile
from pages.utils import VALID_STATUSES, SOURCES, ERIE_SOURCES, run_cli, show_cli_result


def render():
    st.title("🔧 Actions")
    st.caption("Run scraping, scoring, and fetching operations directly from the UI.")

    # ── post-scrape result banner (persists after rerun) ──────────────────────
    if "last_scrape_count" in st.session_state:
        info = st.session_state["last_scrape_count"]
        # Support both old int format and new dict format
        if isinstance(info, dict):
            count   = info.get("count", 0)
            scored  = info.get("scored", 0)
            no_desc = info.get("no_desc", 0)
        else:
            count, scored, no_desc = info, 0, 0

        score_note = ""
        if scored:
            score_note = f" **{scored} scored** (jobs below your 40-pt filter are hidden)."
        if no_desc:
            score_note += f" **{no_desc} pending descriptions** — open each card to paste the full JD, then score manually."

        st.success(
            f"Done! Found **{count} new job(s)**."
            + (score_note or " Go to **📋 Job Board** to review your matches.")
        )

        if st.session_state.get("last_fetch_warning"):
            st.warning(f"Description fetch issue:\n\n```\n{st.session_state['last_fetch_warning']}\n```")
        if st.session_state.get("last_score_warning"):
            st.warning(f"Auto-scoring issue:\n\n```\n{st.session_state['last_score_warning']}\n```")

        if st.button("Dismiss", key="dismiss_scrape_banner"):
            for k in ("last_scrape_count", "last_fetch_warning", "last_score_warning"):
                st.session_state.pop(k, None)
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
                help=(
                    "Specific search terms, space-separated. Each word is matched independently "
                    "against job titles — keep them precise. "
                    "Good: 'SDET QA Appium'. Too broad: 'Mobile Engineer Software'."
                ),
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
                        scrape_errors.append(f"Remote scrape failed — see output below.")

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
                            scrape_errors.append(f"Local scrape failed — see output below.")
                    else:
                        output_lines.append("⚠️ Local pass skipped — LinkedIn and/or Indeed must be selected.")

                if scrape_errors:
                    st.error("Scraping encountered errors:\n\n" + "\n\n".join(scrape_errors))
                st.code("\n\n".join(output_lines))

                # ── auto-fetch descriptions (LinkedIn, Indeed, Dice need this) ──
                from scrapers.linkedin import _SUPPORTED_SOURCES
                no_desc = [j for j in get_jobs_without_description() if j.get("source") in _SUPPORTED_SOURCES]
                if no_desc:
                    with st.spinner(f"Fetching descriptions for {len(no_desc)} job(s)… (headless browser)"):
                        fetch_out, fetch_ok = run_cli(["main.py", "fetch"])
                    if not fetch_ok:
                        st.session_state["last_fetch_warning"] = fetch_out
                    else:
                        st.session_state.pop("last_fetch_warning", None)

                # ── auto-score all jobs that now have descriptions ────────────
                unscored = get_unscored_jobs()
                scored_count = 0
                if unscored:
                    with st.spinner(f"Scoring {len(unscored)} job(s) with Claude AI…"):
                        score_out, score_ok = run_cli(["main.py", "score"])
                    if not score_ok:
                        st.session_state["last_score_warning"] = score_out
                    else:
                        scored_count = len(unscored)
                        st.session_state.pop("last_score_warning", None)

                new_jobs = get_all_jobs(status="new")
                still_no_desc = len([j for j in get_jobs_without_description() if j.get("source") in _SUPPORTED_SOURCES])
                st.session_state["last_scrape_count"] = {
                    "count":   len(new_jobs),
                    "scored":  scored_count,
                    "no_desc": still_no_desc,
                }
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

    # ── scheduler ─────────────────────────────────────────────────────────────
    with st.expander("⏰ Auto-Scrape Scheduler"):
        st.markdown(
            "Run the full scrape → fetch → score pipeline automatically in the background. "
            "Get an email when high-score jobs appear."
        )
        _prof = load_profile()
        _sched = _prof.get("scheduler", {})

        sc1, sc2 = st.columns(2)
        with sc1:
            sched_enabled = st.toggle("Enable scheduler", value=bool(_sched.get("enabled")))
            sched_interval = st.selectbox(
                "Run every",
                [2, 4, 6, 8, 12, 24],
                index=[2, 4, 6, 8, 12, 24].index(int(_sched.get("interval_hours", 6))),
                format_func=lambda h: f"{h} hours",
            )
            sched_min_score = st.slider(
                "Notify when score ≥",
                min_value=50, max_value=95, step=5,
                value=int(_sched.get("min_score_alert", 70)),
            )
        with sc2:
            st.markdown("**Email notifications** *(optional)*")
            st.caption("Uses Gmail SMTP. Create an [App Password](https://myaccount.google.com/apppasswords) — not your real password.")
            sched_smtp_from  = st.text_input("Your Gmail address", value=_sched.get("smtp_from", ""), placeholder="you@gmail.com")
            sched_smtp_pass  = st.text_input("App password (16 chars)", value=_sched.get("smtp_password", ""), type="password", placeholder="xxxx xxxx xxxx xxxx")
            sched_notify     = st.text_input("Send alerts to", value=_sched.get("notify_email", ""), placeholder="same as above, or another address")

        if st.button("💾 Save Scheduler Settings"):
            _prof["scheduler"] = {
                "enabled":         sched_enabled,
                "interval_hours":  sched_interval,
                "min_score_alert": sched_min_score,
                "smtp_from":       sched_smtp_from.strip(),
                "smtp_password":   sched_smtp_pass.strip(),
                "notify_email":    sched_notify.strip(),
            }
            save_profile(_prof)
            st.toast("Scheduler settings saved!", icon="✅")

        # Last run status
        import json as _json
        _state_path = os.path.join(os.path.dirname(__file__), "..", "scheduler_state.json")
        if os.path.exists(_state_path):
            try:
                with open(_state_path) as _f:
                    _state = _json.load(_f)
                st.caption(
                    f"Last run: **{_state.get('last_run', 'never')}** — "
                    f"found {_state.get('last_found', 0)} high-score job(s)"
                )
            except Exception:
                pass

        if st.button("▶ Run Pipeline Now", help="Trigger scrape → fetch → score + email notification immediately"):
            with st.spinner("Running full pipeline… (may take a few minutes)"):
                _kw = _prof.get("target_role", "").strip()
                if _kw:
                    out1, ok1 = run_cli(["main.py", "scrape", "--keywords", _kw])
                    out2, ok2 = run_cli(["main.py", "fetch"])
                    out3, ok3 = run_cli(["main.py", "score"])
                    combined  = "\n\n".join([out1, out2, out3])
                    show_cli_result(combined, ok1 and ok2 and ok3)

                    # ── send notification if email configured ─────────────────
                    _sched_cfg = load_profile().get("scheduler", {})
                    _min       = int(_sched_cfg.get("min_score_alert", 70))
                    from scheduler import _get_new_high_score_jobs, _send_email
                    # Only look at jobs scraped in the last 60 min (this run)
                    _hits = _get_new_high_score_jobs(_min, since_minutes=60)
                    if _hits:
                        _ok, _err = _send_email(_sched_cfg, _hits)
                        if _ok:
                            st.success(f"📧 Email sent — {len(_hits)} new job(s) scored {_min}+.")
                        elif _err and ("not configured" in _err):
                            st.info(f"Found {len(_hits)} new job(s) scored {_min}+ but email is not configured.")
                        else:
                            st.warning(f"Found {len(_hits)} new job(s) scored {_min}+ but email failed: {_err}")
                    else:
                        st.info(f"No new jobs from this run scored {_min}+ — no email sent.")
                else:
                    st.warning("Set a Target Role in your Profile first.")

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
