# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
"""
User profile — name, contact info, resume text, and resume slots.
Stored in profile.json at the repo root.
"""

import json
import os

PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "profile.json")

DEFAULT_PROFILE = {
    "name":           "",
    "email":          "",
    "linkedin":       "",
    "github":         "",
    "website":        "",
    "location":       "",
    "title":          "",
    "target_role":    "",
    "resume":         "",
    "writing_sample": "",
    # Multiple resume slots — {"Default": "...", "Senior IC": "..."}
    "resumes":        {},
    "active_resume":  "",
    # Scheduler / notification config
    "scheduler": {
        "enabled":         False,
        "interval_hours":  6,
        "min_score_alert": 70,
        "location":        "Remote US",
        "notify_email":    "",
        "smtp_from":       "",
        "smtp_password":   "",
    },
}


def _ensure_slots(profile: dict) -> dict:
    """
    Backward-compat migration: if resumes dict is empty/missing,
    seed it from the bare 'resume' field as a 'Default' slot.
    Always keeps profile['resume'] in sync with the active slot.
    """
    if not profile.get("resumes"):
        resume_text = profile.get("resume", "")
        profile["resumes"] = {"Default": resume_text}
        profile["active_resume"] = "Default"
    elif not profile.get("active_resume") or profile["active_resume"] not in profile["resumes"]:
        profile["active_resume"] = next(iter(profile["resumes"]))

    # Keep the flat 'resume' field in sync — scorer/tailor read this
    active = profile["active_resume"]
    profile["resume"] = profile["resumes"].get(active, "")
    return profile


def _ensure_scheduler(profile: dict) -> dict:
    """Ensure scheduler dict has all expected keys (handles old profiles)."""
    default_sched = DEFAULT_PROFILE["scheduler"].copy()
    existing = profile.get("scheduler") or {}
    profile["scheduler"] = {**default_sched, **existing}
    return profile


def load_profile() -> dict:
    if not os.path.exists(PROFILE_PATH):
        return _ensure_slots(_ensure_scheduler(DEFAULT_PROFILE.copy()))
    with open(PROFILE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    profile = {**DEFAULT_PROFILE, **data}
    profile = _ensure_slots(profile)
    profile = _ensure_scheduler(profile)
    return profile


def save_profile(profile: dict):
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
