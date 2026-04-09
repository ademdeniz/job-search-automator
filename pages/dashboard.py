# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
import streamlit as st
import pandas as pd
from storage.database import get_all_jobs, stats


def render():
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

    # ── application analytics ─────────────────────────────────────────────────
    st.divider()
    st.subheader("📊 Application Analytics")

    all_jobs = get_all_jobs()
    applied_jobs   = [j for j in all_jobs if j["status"] in ("applied", "interviewing", "offer")]
    got_response   = [j for j in all_jobs if j["status"] in ("interviewing", "offer")]
    scored_applied = [j for j in applied_jobs if j.get("score") is not None]
    scored_response = [j for j in got_response if j.get("score") is not None]

    an1, an2, an3 = st.columns(3)

    total_applied  = len(applied_jobs)
    total_response = len(got_response)
    response_rate  = round(total_response / total_applied * 100, 1) if total_applied else 0
    an1.metric("Overall Response Rate", f"{response_rate}%", f"{total_response} of {total_applied} applications")

    avg_resp   = round(sum(j["score"] for j in scored_response) / len(scored_response), 1) if scored_response else 0
    no_resp    = [j for j in scored_applied if j["status"] == "applied"]
    avg_noresp = round(sum(j["score"] for j in no_resp) / len(no_resp), 1) if no_resp else 0
    an2.metric("Avg Score — Got Response", f"{avg_resp}/100")
    an3.metric("Avg Score — No Response", f"{avg_noresp}/100")

    st.markdown("")
    ac1, ac2 = st.columns(2)

    # ── Response rate by source ───────────────────────────────────────────────
    with ac1:
        st.markdown("**Response Rate by Source**")
        source_applied  = {}
        source_response = {}
        for j in applied_jobs:
            src = j.get("source") or "unknown"
            source_applied[src] = source_applied.get(src, 0) + 1
        for j in got_response:
            src = j.get("source") or "unknown"
            source_response[src] = source_response.get(src, 0) + 1

        if source_applied:
            src_rows = []
            for src, cnt in sorted(source_applied.items(), key=lambda x: -x[1]):
                resp = source_response.get(src, 0)
                rate = round(resp / cnt * 100, 1) if cnt else 0
                src_rows.append({"Source": src, "Applied": cnt, "Response": resp, "Rate %": rate})
            src_df = pd.DataFrame(src_rows)
            st.dataframe(src_df, use_container_width=True, hide_index=True)
        else:
            st.info("No applications tracked yet.")

    # ── Score distribution: responded vs not ─────────────────────────────────
    with ac2:
        st.markdown("**Score Distribution: Response vs No Response**")
        if scored_response or no_resp:
            bins   = [0, 25, 50, 75, 90, 101]
            labels = ["0-24", "25-49", "50-74", "75-89", "90+"]

            def _bin_scores(jobs):
                counts = {l: 0 for l in labels}
                for j in jobs:
                    s = j["score"]
                    for i, (lo, hi) in enumerate(zip(bins, bins[1:])):
                        if lo <= s < hi:
                            counts[labels[i]] += 1
                            break
                return counts

            resp_bins   = _bin_scores(scored_response)
            noresp_bins = _bin_scores(no_resp)
            dist_df = pd.DataFrame({
                "Range":        labels,
                "Got Response": [resp_bins[l] for l in labels],
                "No Response":  [noresp_bins[l] for l in labels],
            }).set_index("Range")
            st.bar_chart(dist_df)
        else:
            st.info("Score more jobs to see distribution.")
