# Copyright (c) 2025 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
"""
User profile — name, contact info, and resume text.
Stored in profile.json at the repo root.
"""

import json
import os

PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "profile.json")

DEFAULT_PROFILE = {
    "name":     "",
    "email":    "",
    "linkedin": "",
    "github":   "",
    "website":  "",
    "location": "",
    "resume":   "",
}


def load_profile() -> dict:
    if not os.path.exists(PROFILE_PATH):
        return DEFAULT_PROFILE.copy()
    with open(PROFILE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {**DEFAULT_PROFILE, **data}


def save_profile(profile: dict):
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
