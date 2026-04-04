"""
Greenhouse ATS — Review-mode auto-applier using Playwright.

Opens the job application form in a VISIBLE browser, pre-fills all standard
fields, attaches the tailored resume and cover letter, then pauses so the
candidate can review everything and click Submit themselves.

No auto-submit — the human always has the final say.
"""

import os
import re
import time
import glob as _glob
from typing import Optional

# Candidate profile — edit these once, used across all applications
CANDIDATE = {
    "first_name": "Adem",
    "last_name":  "Garic",
    "email":      "ademdenizgaric@gmail.com",
    "phone":      "8145662086",
    "linkedin":   "https://www.linkedin.com/in/adem-garic-sdet-qa/",
    "github":     "https://github.com/ademdeniz",
    "website":    "https://github.com/ademdeniz",
    "location":   "Erie, Pennsylvania, United States",
    # Screening answers
    "work_auth":           "Yes",
    "sponsorship":         "No",
    "previously_employed": "No",
    "in_listed_states":    "No",   # Alabama, Alaska, etc. — Erie PA is not in that list
    "privacy_consent":     "Yes",
}

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")


def _find_docx(job: dict, file_type: str) -> Optional[str]:
    title   = job.get("title", "")
    company = job.get("company", "")
    raw     = f"{title}_{company}"
    slug    = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")[:60]
    path    = os.path.join(OUTPUT_DIR, slug, f"{file_type}.docx")
    if os.path.exists(path):
        return path
    matches = _glob.glob(os.path.join(OUTPUT_DIR, "*", f"{file_type}.docx"))
    return matches[0] if matches else None


def _scroll_and_fill(page, selector: str, value: str):
    """Scroll element into view then fill it."""
    try:
        el = page.query_selector(selector)
        if el:
            el.scroll_into_view_if_needed()
            time.sleep(0.3)
            tag = el.evaluate("e => e.tagName.toLowerCase()")
            if tag == "select":
                # 1. Try exact label match
                try:
                    el.select_option(label=value)
                    return True
                except Exception:
                    pass
                # 2. Try partial text match on options
                options = el.query_selector_all("option")
                for opt in options:
                    opt_text = (opt.inner_text() or "").strip()
                    if not opt_text or opt_text.lower() in ("select...", "select", ""):
                        continue
                    if value.lower() in opt_text.lower():
                        opt_val = opt.get_attribute("value")
                        el.select_option(value=opt_val)
                        return True
                # 3. For Yes/consent answers — pick first option containing
                #    "yes", "i acknowledge", "i have read", "i agree"
                if value.lower() in ("yes", "i acknowledge"):
                    CONSENT_PHRASES = ("yes", "i acknowledge", "i have read", "i agree", "i certify")
                    for opt in options:
                        opt_text = (opt.inner_text() or "").strip().lower()
                        if any(p in opt_text for p in CONSENT_PHRASES):
                            opt_val = opt.get_attribute("value")
                            el.select_option(value=opt_val)
                            return True
            else:
                el.fill(value)
                return True
    except Exception:
        pass
    return False


def _fill_by_label(page, label_text: str, value: str) -> bool:
    """Find an input by its label text and fill it. Handles both select and text inputs."""
    try:
        labels = page.query_selector_all("label")
        for lbl in labels:
            text = (lbl.inner_text() or "").strip()
            if label_text.lower() in text.lower():
                for_id = lbl.get_attribute("for")
                if for_id:
                    lbl.scroll_into_view_if_needed()
                    time.sleep(0.2)
                    return _scroll_and_fill(page, f"#{for_id}", value)
    except Exception:
        pass
    return False


def _upload_if_exists(page, selector: str, file_path: Optional[str]):
    if not file_path or not os.path.exists(file_path):
        return False
    try:
        el = page.query_selector(selector)
        if el:
            el.set_input_files(file_path)
            return True
    except Exception:
        pass
    return False


def apply_greenhouse(job: dict, headless: bool = False) -> dict:
    """
    Open the Greenhouse application form for a job in review mode.
    Pre-fills all standard fields and pauses for human review before submit.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        return {"ok": False, "error": "playwright not installed"}

    url = job.get("url", "")
    if not url:
        return {"ok": False, "error": "Job has no URL"}

    if "greenhouse.io" not in url:
        return {"ok": False, "error": "Not a Greenhouse job URL"}

    resume_path = _find_docx(job, "resume")
    cl_path     = _find_docx(job, "cover_letter")
    filled  = []
    missing = []
    warnings = []

    if not resume_path:
        warnings.append("No tailored resume found — run 'Tailor Resume' first.")
    if not cl_path:
        warnings.append("No cover letter found — run 'Tailor Resume + Cover Letter' first.")

    print(f"\n[Apply] {job.get('title')} @ {job.get('company')}")
    print(f"[Apply] {url}")
    if resume_path:  print(f"[Apply] Resume:       {resume_path}")
    if cl_path:      print(f"[Apply] Cover letter: {cl_path}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=80)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
        except PWTimeout:
            browser.close()
            return {"ok": False, "error": "Page load timed out"}

        # ── 1. Basic personal info ─────────────────────────────────────────────
        for sel, val, lbl in [
            ("#first_name", CANDIDATE["first_name"], "First name"),
            ("#last_name",  CANDIDATE["last_name"],  "Last name"),
            ("#email",      CANDIDATE["email"],       "Email"),
            ("#phone",      CANDIDATE["phone"],       "Phone"),
        ]:
            if _scroll_and_fill(page, sel, val):
                filled.append(lbl)

        # ── 2. Resume upload ───────────────────────────────────────────────────
        if _upload_if_exists(page, "#resume", resume_path):
            filled.append("Resume")
        else:
            missing.append("Resume")

        # ── 3. Cover letter upload ─────────────────────────────────────────────
        for sel in ["#cover_letter", "input[id*='cover']", "input[name*='cover']"]:
            if _upload_if_exists(page, sel, cl_path):
                filled.append("Cover letter")
                break

        # Scroll down to reveal all dynamic fields
        page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        time.sleep(1)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1.5)

        # ── 4. Social / profile links (label-matched) ─────────────────────────
        for label, value in [
            ("LinkedIn Profile",   CANDIDATE["linkedin"]),
            ("LinkedIn",           CANDIDATE["linkedin"]),
            ("Github",             CANDIDATE["github"]),
            ("GitHub",             CANDIDATE["github"]),
            ("Website",            CANDIDATE["website"]),
            ("Portfolio",          CANDIDATE["website"]),
            ("Twitter",            ""),   # leave blank
        ]:
            if _fill_by_label(page, label, value) and value:
                filled.append(label)

        # ── 5. Screening questions — label-pattern matched ────────────────────
        # Map label substrings → answers. Longer/more specific patterns first.
        SCREENING = [
            ("previously been employed",            CANDIDATE["previously_employed"]),
            ("previously employed",                 CANDIDATE["previously_employed"]),
            ("require.*visa.*sponsor",              CANDIDATE["sponsorship"]),
            ("require.*sponsor",                    CANDIDATE["sponsorship"]),
            ("visa sponsorship",                    CANDIDATE["sponsorship"]),
            ("sponsorship",                         CANDIDATE["sponsorship"]),
            ("authorized to work",                  CANDIDATE["work_auth"]),
            ("work authorization",                  CANDIDATE["work_auth"]),
            ("authorization to work",               CANDIDATE["work_auth"]),
            ("lawfully.*united states",             CANDIDATE["work_auth"]),
            # State list question (Alabama, Alaska, etc.)
            ("alabama.*alaska.*delaware",           CANDIDATE["in_listed_states"]),
            ("following states",                    CANDIDATE["in_listed_states"]),
            # Privacy / consent — match any acknowledgement or double-check dropdown
            ("privacy notice",                      CANDIDATE["privacy_consent"]),
            ("job applicant privacy",               CANDIDATE["privacy_consent"]),
            ("acknowledge.*privacy",                CANDIDATE["privacy_consent"]),
            ("read and understand",                 CANDIDATE["privacy_consent"]),
            ("double.check",                        CANDIDATE["privacy_consent"]),
            ("double check",                        CANDIDATE["privacy_consent"]),
            ("information provided above",          CANDIDATE["privacy_consent"]),
            ("accuracy is crucial",                 CANDIDATE["privacy_consent"]),
        ]

        try:
            all_labels = page.query_selector_all("label")
            for lbl in all_labels:
                lbl_text = (lbl.inner_text() or "").strip()
                lbl_lower = lbl_text.lower()
                for pattern, answer in SCREENING:
                    if re.search(pattern, lbl_lower):
                        for_id = lbl.get_attribute("for")
                        if for_id and answer:
                            lbl.scroll_into_view_if_needed()
                            time.sleep(0.2)
                            if _scroll_and_fill(page, f"#{for_id}", answer):
                                filled.append(f"Q: {lbl_text[:50]}")
                        break
        except Exception:
            pass

        # Final scroll to top so user sees the full form
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.5)

        # ── PAUSE ─────────────────────────────────────────────────────────────
        print("\n" + "═" * 60)
        print("  REVIEW MODE — browser is open and pre-filled.")
        print(f"  Filled: {', '.join(filled)}")
        if missing:
            print(f"  Missing: {', '.join(missing)}")
        print()
        print("  Still needs YOU:")
        print("  • Demographic questions (gender, race, etc.) — your choice")
        print("  • Any custom open-text questions")
        print("  • Final review of all fields")
        print("  • Click Submit when ready")
        print()
        print("  Press ENTER here to close the browser when done.")
        print("═" * 60 + "\n")

        input()
        browser.close()

    return {"ok": True, "filled": filled, "missing": missing, "warnings": warnings}
