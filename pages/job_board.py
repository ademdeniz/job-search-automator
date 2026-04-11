# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
import os
import re as _re
import streamlit as st
from storage.database import (
    get_all_jobs, update_status, update_job_metadata, update_description,
)
from storage.profile import load_profile
from pages.utils import (
    VALID_STATUSES, SOURCES, SCORE_COLOR, STATUS_COLOR,
    match_level, score_badge, extract_metadata, run_cli, docx_to_pdf, has_libreoffice,
)

AGGREGATORS = {
    "remotehunter", "jobgether", "indeed", "linkedin",
    "glassdoor", "ziprecruiter", "simplyhired", "scoutit",
}


def render():
    st.title("📋 Job Board")

    # ── filters ───────────────────────────────────────────────────────────────
    col1, col2, col3, col4, col5 = st.columns([2, 1.5, 1.5, 1.5, 1])
    with col1:
        keyword = st.text_input("🔍 Search", placeholder="title, company, description…")
    with col2:
        filter_status = st.selectbox("Status", ["New only", "All"])
    with col3:
        filter_source = st.selectbox("Source", ["All"] + SOURCES)
    with col4:
        min_score = st.slider("Min Score", 0, 100, 0, step=5)
    with col5:
        remote_only = st.checkbox("Remote only")

    sort_by = st.radio("Sort by", ["Score ↓", "Date ↓"], horizontal=True)

    status_filter = "new" if filter_status == "New only" else None

    jobs = get_all_jobs(
        status=status_filter,
        source=None if filter_source == "All" else filter_source,
        keyword=keyword or None,
        remote=True if remote_only else None,
    )

    # Always exclude pipeline and rejected jobs — they live in My Applications
    _excluded = {"applied", "interviewing", "offer", "rejected"}
    if status_filter is None:
        jobs = [j for j in jobs if j["status"] not in _excluded]

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
                        import json as _json
                        _highlights = job["score_reason"].split(" | ")[0]
                        st.markdown(f"**AI Analysis:** {_highlights}")

                        def _parse_skills(col):
                            raw = job.get(col)
                            if not raw:
                                return []
                            try:
                                return _json.loads(raw)
                            except Exception:
                                return []

                        _matched  = _parse_skills("matched_skills")
                        _missing  = _parse_skills("missing_skills")
                        _keywords = _parse_skills("suggested_keywords")

                        if _matched or _missing or _keywords:
                            def _chips(items, color):
                                return " ".join(
                                    f'<span style="background:{color}22;color:{color};'
                                    f'padding:1px 8px;border-radius:99px;font-size:0.78rem;'
                                    f'margin:2px;display:inline-block;">{s}</span>'
                                    for s in items
                                )
                            parts = []
                            if _matched:
                                parts.append(f"✅ &nbsp;{_chips(_matched, '#22c55e')}")
                            if _missing:
                                parts.append(f"❌ &nbsp;{_chips(_missing, '#ef4444')}")
                            if _keywords:
                                parts.append(f"💡 &nbsp;{_chips(_keywords, '#f59e0b')}")
                            st.markdown(
                                "<div style='margin:6px 0 10px 0;line-height:2;'>"
                                + "<br>".join(parts)
                                + "</div>",
                                unsafe_allow_html=True,
                            )

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

                    has_desc = len(job.get("description") or "") >= 30
                    manual_key = f"manual_desc_{job['id']}"
                    is_aggregator = job.get("company", "").lower().strip() in AGGREGATORS
                    company_override_key = f"company_override_{job['id']}"

                    if is_aggregator:
                        st.warning(f"⚠️ Listed via **{job['company']}** — enter the real company name below.")
                        st.text_input("Real company name", key=company_override_key, placeholder="e.g. Veracyte")

                    if has_desc and (not job.get("posted_date") or not job.get("job_type")):
                        if st.button("🔍 Extract metadata from description", key=f"extract_meta_{job['id']}"):
                            meta = extract_metadata(job.get("description", ""))
                            if meta:
                                update_job_metadata(job["id"], **meta)
                                st.success(f"Extracted: {', '.join(f'{k}={v}' for k,v in meta.items())}")
                                st.rerun()
                            else:
                                st.info("No metadata found in description.")

                    paste_label = "Paste full job description (replaces scraped snippet)" if has_desc else "Paste job description"
                    if not has_desc:
                        st.warning("⚠️ No description yet — tailoring is disabled until you paste one below.")
                    manual_desc = st.text_area(
                        paste_label,
                        key=manual_key,
                        height=160,
                        placeholder="Copy the full job description from the job board and paste it here…",
                    )
                    if manual_desc and st.button("💾 Save description", key=f"save_desc_{job['id']}"):
                        update_description(job["id"], manual_desc)
                        meta = extract_metadata(manual_desc)
                        if meta:
                            update_job_metadata(job["id"], **meta)
                        st.success(
                            "Description saved."
                            + (f" Extracted: {', '.join(f'{k}={v}' for k,v in meta.items())}" if meta else "")
                        )
                        st.rerun()

                    tailor_desc = st.session_state.get(manual_key, "") or job.get("description", "")
                    can_tailor = bool(tailor_desc.strip())

                    if st.button(
                        "✍️ Tailor Resume + Cover Letter",
                        key=f"tailor_{job['id']}",
                        disabled=not can_tailor,
                        type="primary",
                    ):
                        if not has_desc and tailor_desc:
                            update_description(job["id"], tailor_desc)

                        override = st.session_state.get(company_override_key, "").strip()
                        with st.spinner("Claude is tailoring your resume… (30–60 sec)"):
                            out, ok = run_cli(["main.py", "tailor", str(job["id"])]
                                             + (["--company", override] if override else []))

                        if not ok:
                            st.error(f"Tailoring failed:\n\n```\n{out}\n```")
                        else:
                            resume_match  = _re.search(r"Resume:\s+(.+\.docx)", out)
                            cl_match      = _re.search(r"Cover letter:\s+(.+\.docx)", out)
                            company_match = _re.search(r"Real company identified:\s+(.+?)\s+\(was:", out)
                            real_company  = company_match.group(1).strip() if company_match else job["company"]
                            st.session_state[f"tailor_files_{job['id']}"] = {
                                "resume": resume_match.group(1).strip() if resume_match else None,
                                "cover_letter": cl_match.group(1).strip() if cl_match else None,
                                "company": real_company,
                                "log": out,
                            }

                    state_key = f"tailor_files_{job['id']}"
                    if state_key in st.session_state:
                        files = st.session_state[state_key]
                        if files.get("log"):
                            st.code(files["log"])

                        log = files.get("log", "")
                        if "[ATS] ✅" in log:
                            st.success("ATS Check: Resume passed")
                        elif "[ATS] ⚠️" in log:
                            issues = [
                                line.strip().lstrip("•").strip()
                                for line in log.splitlines()
                                if line.strip().startswith("•")
                            ]
                            st.warning("ATS Check: Issues found\n" + ("\n".join(f"• {i}" for i in issues) if issues else ""))

                        dl_col1, dl_col2 = st.columns(2)
                        co = files.get("company", job["company"]).replace(" ", "_")
                        if files.get("resume") and os.path.exists(files["resume"]):
                            with open(files["resume"], "rb") as f:
                                dl_col1.download_button(
                                    "⬇ Resume.docx", data=f.read(),
                                    file_name=f"resume_{co}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"dl_resume_{job['id']}",
                                )
                            if has_libreoffice():
                                pdf = docx_to_pdf(files["resume"])
                                if pdf and os.path.exists(pdf):
                                    with open(pdf, "rb") as f:
                                        dl_col1.download_button(
                                            "⬇ Resume.pdf", data=f.read(),
                                            file_name=f"resume_{co}.pdf",
                                            mime="application/pdf",
                                            key=f"dl_resume_pdf_{job['id']}",
                                        )
                        if files.get("cover_letter") and os.path.exists(files["cover_letter"]):
                            with open(files["cover_letter"], "rb") as f:
                                dl_col2.download_button(
                                    "⬇ Cover Letter.docx", data=f.read(),
                                    file_name=f"cover_letter_{co}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"dl_cl_{job['id']}",
                                )
                            if has_libreoffice():
                                pdf = docx_to_pdf(files["cover_letter"])
                                if pdf and os.path.exists(pdf):
                                    with open(pdf, "rb") as f:
                                        dl_col2.download_button(
                                            "⬇ Cover Letter.pdf", data=f.read(),
                                            file_name=f"cover_letter_{co}.pdf",
                                            mime="application/pdf",
                                            key=f"dl_cl_pdf_{job['id']}",
                                        )
