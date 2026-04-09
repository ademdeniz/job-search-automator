# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
import streamlit as st
from storage.profile import load_profile, save_profile


def render():
    st.title("👤 Profile")
    st.caption("Your info is used for resume tailoring and cover letter generation.")

    profile = load_profile()

    st.subheader("Contact Info")
    c1, c2 = st.columns(2)
    with c1:
        p_name     = st.text_input("Full name",  value=profile.get("name", ""))
        p_email    = st.text_input("Email",       value=profile.get("email", ""))
        p_location = st.text_input("Location",   value=profile.get("location", ""),
                                   placeholder="e.g. Erie, PA")
        p_title = st.text_input(
            "Professional title",
            value=profile.get("title", ""),
            placeholder="e.g. Senior Software Engineer / Product Designer / HR Manager",
            help="Appears under your name in the cover letter signature.",
        )
        p_target_role = st.text_input(
            "Target role / keywords",
            value=profile.get("target_role", ""),
            placeholder="e.g. software engineer Python React  /  UX designer Figma  /  HR business partner",
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
    st.subheader("Writing Sample")
    st.caption(
        "Paste a paragraph or two you actually wrote — a LinkedIn post, an email, a personal essay, "
        "anything informal. Claude uses this to match your natural voice in cover letters. "
        "The more unfiltered the better."
    )
    p_writing_sample = st.text_area(
        "Writing sample",
        value=profile.get("writing_sample", ""),
        height=200,
        label_visibility="collapsed",
        placeholder="Paste something you wrote naturally, not for a job application…",
    )

    st.divider()
    if st.button("💾 Save Profile", type="primary"):
        save_profile({
            "name":           p_name.strip(),
            "email":          p_email.strip(),
            "linkedin":       p_linkedin.strip(),
            "github":         p_github.strip(),
            "website":        p_website.strip(),
            "location":       p_location.strip(),
            "title":          p_title.strip(),
            "target_role":    p_target_role.strip(),
            "resume":         p_resume.strip(),
            "writing_sample": p_writing_sample.strip(),
        })
        st.toast("Profile saved!", icon="✅")
