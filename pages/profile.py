# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
import streamlit as st
from storage.profile import load_profile, save_profile


def render():
    st.title("👤 Profile")
    st.caption("Your info is used for resume tailoring and cover letter generation.")

    profile = load_profile()

    # ── contact info ──────────────────────────────────────────────────────────
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
            placeholder="e.g. SDET Appium  /  UX Figma  /  HR recruiter",
            help=(
                "Used as default search keywords when scraping. "
                "Use specific terms, not a full job title — each word is matched independently. "
                "Tip: 2-4 precise terms work better than a long phrase."
            ),
        )
    with c2:
        p_linkedin = st.text_input("LinkedIn URL", value=profile.get("linkedin", ""),
                                   placeholder="linkedin.com/in/your-handle")
        p_github   = st.text_input("GitHub URL",   value=profile.get("github", ""),
                                   placeholder="github.com/yourhandle")
        p_website  = st.text_input("Website / Portfolio", value=profile.get("website", ""),
                                   placeholder="yourportfolio.com (optional)")

    # ── resume slots ──────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Resume")
    st.caption(
        "Maintain multiple resume versions for different role types — "
        "e.g. *Senior IC*, *Manager track*, *Startup*. "
        "The **active slot** is what Claude uses for scoring and tailoring."
    )

    resumes = profile.get("resumes", {})
    active  = profile.get("active_resume", "")
    slots   = list(resumes.keys())

    # ── slot selector + add ───────────────────────────────────────────────────
    sl1, sl2, sl3 = st.columns([3, 2, 1])
    with sl1:
        selected_slot = st.selectbox(
            "Active slot",
            slots,
            index=slots.index(active) if active in slots else 0,
            key="slot_select",
        )
    with sl2:
        new_slot_name = st.text_input(
            "New slot name",
            placeholder="e.g. Senior IC",
            label_visibility="collapsed",
            key="new_slot_name",
        )
    with sl3:
        if st.button("➕ Add slot", use_container_width=True, key="add_slot_btn"):
            name = new_slot_name.strip()
            if name and name not in resumes:
                resumes[name] = ""
                profile["resumes"] = resumes
                profile["active_resume"] = name
                profile["resume"] = ""
                save_profile(profile)
                st.rerun()
            elif name in resumes:
                st.warning(f"Slot '{name}' already exists.")

    # ── switch active slot ────────────────────────────────────────────────────
    if selected_slot != active:
        profile["active_resume"] = selected_slot
        profile["resume"] = resumes.get(selected_slot, "")
        save_profile(profile)
        st.rerun()

    # ── delete slot (only if more than one) ───────────────────────────────────
    if len(slots) > 1:
        if st.button(f"🗑 Delete '{selected_slot}'", key="delete_slot_btn"):
            del resumes[selected_slot]
            profile["resumes"] = resumes
            profile["active_resume"] = next(iter(resumes))
            profile["resume"] = resumes[profile["active_resume"]]
            save_profile(profile)
            st.rerun()

    # ── resume text area for active slot ──────────────────────────────────────
    p_resume = st.text_area(
        f"Resume — {selected_slot}",
        value=resumes.get(selected_slot, ""),
        height=500,
        label_visibility="collapsed",
        placeholder="Paste your resume here…",
    )

    # ── writing sample ────────────────────────────────────────────────────────
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

    # ── save ──────────────────────────────────────────────────────────────────
    st.divider()
    if st.button("💾 Save Profile", type="primary"):
        updated_resumes = dict(resumes)
        updated_resumes[selected_slot] = p_resume.strip()
        save_profile({
            **profile,
            "name":           p_name.strip(),
            "email":          p_email.strip(),
            "linkedin":       p_linkedin.strip(),
            "github":         p_github.strip(),
            "website":        p_website.strip(),
            "location":       p_location.strip(),
            "title":          p_title.strip(),
            "target_role":    p_target_role.strip(),
            "resume":         p_resume.strip(),
            "resumes":        updated_resumes,
            "active_resume":  selected_slot,
            "writing_sample": p_writing_sample.strip(),
        })
        st.toast("Profile saved!", icon="✅")
