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
    "location":   "Erie, Pennsylvania, United States",
    # Standard answers to common screening questions
    "work_auth":  "Yes",           # authorized to work in US
    "sponsorship": "No",           # does not require sponsorship
    "previously_employed": "No",   # not previously employed at this company
}

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")


def _find_docx(job: dict, file_type: str) -> Optional[str]:
    """Find the tailored resume or cover letter .docx for this job."""
    title   = job.get("title", "")
    company = job.get("company", "")
    raw     = f"{title}_{company}"
    slug    = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")[:60]
    path    = os.path.join(OUTPUT_DIR, slug, f"{file_type}.docx")
    if os.path.exists(path):
        return path
    # Fallback: any .docx in any output subfolder matching file_type
    matches = _glob.glob(os.path.join(OUTPUT_DIR, "*", f"{file_type}.docx"))
    return matches[0] if matches else None


def _fill_if_exists(page, selector: str, value: str, method="fill"):
    """Fill a field only if it exists on the page — silently skip if not."""
    try:
        el = page.query_selector(selector)
        if el and el.is_visible():
            if method == "fill":
                el.fill(value)
            elif method == "select":
                el.select_option(label=value)
    except Exception:
        pass


def _upload_if_exists(page, selector: str, file_path: Optional[str]):
    """Attach a file only if the input exists and the file is on disk."""
    if not file_path or not os.path.exists(file_path):
        return
    try:
        el = page.query_selector(selector)
        if el:
            el.set_input_files(file_path)
    except Exception:
        pass


def apply_greenhouse(job: dict, headless: bool = False) -> dict:
    """
    Open the Greenhouse application form for a job in review mode.

    - headless=False  → visible browser (default for review mode)
    - Returns a status dict with what was filled and any warnings.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        return {"ok": False, "error": "playwright not installed"}

    url = job.get("url", "")
    if not url:
        return {"ok": False, "error": "Job has no URL"}

    # Greenhouse apply URLs — convert board URL to apply URL if needed
    # boards.greenhouse.io/company/jobs/ID  →  boards.greenhouse.io/company/jobs/ID
    # (Greenhouse uses the same URL for the application form)
    if "greenhouse.io" not in url and "lever.co" not in url:
        return {"ok": False, "error": "Not a Greenhouse job URL"}

    resume_path = _find_docx(job, "resume")
    cl_path     = _find_docx(job, "cover_letter")

    filled  = []
    missing = []
    warnings = []

    if not resume_path:
        warnings.append("No tailored resume found — run 'Tailor Resume' first for best results.")
    if not cl_path:
        warnings.append("No cover letter found — run 'Tailor Resume + Cover Letter' first.")

    print(f"[Apply] Opening Greenhouse form for: {job.get('title')} @ {job.get('company')}")
    print(f"[Apply] URL: {url}")
    if resume_path:
        print(f"[Apply] Resume:       {resume_path}")
    if cl_path:
        print(f"[Apply] Cover letter: {cl_path}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=100)
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

        # ── Standard personal info fields ─────────────────────────────────────
        for field_id, value, label in [
            ("#first_name",  CANDIDATE["first_name"], "First name"),
            ("#last_name",   CANDIDATE["last_name"],  "Last name"),
            ("#email",       CANDIDATE["email"],       "Email"),
            ("#phone",       CANDIDATE["phone"],       "Phone"),
        ]:
            _fill_if_exists(page, field_id, value)
            filled.append(label)

        # ── LinkedIn (question field — label-matched) ─────────────────────────
        for q_label, value in [
            ("LinkedIn Profile", CANDIDATE["linkedin"]),
        ]:
            try:
                # Find input whose associated label contains the text
                labels = page.query_selector_all("label")
                for lbl in labels:
                    if q_label.lower() in (lbl.inner_text() or "").lower():
                        for_id = lbl.get_attribute("for")
                        if for_id:
                            _fill_if_exists(page, f"#{for_id}", value)
                            filled.append(q_label)
                            break
            except Exception:
                pass

        # ── Resume upload ─────────────────────────────────────────────────────
        _upload_if_exists(page, "#resume", resume_path)
        if resume_path:
            filled.append("Resume")
        else:
            missing.append("Resume (tailor first)")

        # ── Cover letter upload ───────────────────────────────────────────────
        # Greenhouse cover letter field varies — try common selectors
        for cl_selector in ["#cover_letter", "input[id*='cover']", "input[name*='cover']"]:
            try:
                el = page.query_selector(cl_selector)
                if el:
                    _upload_if_exists(page, cl_selector, cl_path)
                    if cl_path:
                        filled.append("Cover letter")
                    break
            except Exception:
                pass

        # ── Common screening questions (label-based matching) ─────────────────
        SCREENING = {
            "authorized to work": CANDIDATE["work_auth"],
            "work authorization": CANDIDATE["work_auth"],
            "require.*sponsor":   CANDIDATE["sponsorship"],
            "sponsorship":        CANDIDATE["sponsorship"],
            "previously employed": CANDIDATE["previously_employed"],
            "previously been employed": CANDIDATE["previously_employed"],
        }

        try:
            all_labels = page.query_selector_all("label")
            for lbl in all_labels:
                lbl_text = (lbl.inner_text() or "").lower()
                for pattern, answer in SCREENING.items():
                    if re.search(pattern, lbl_text):
                        for_id = lbl.get_attribute("for")
                        if for_id:
                            # Try select first, then fill
                            el = page.query_selector(f"#{for_id}")
                            if el:
                                tag = el.evaluate("e => e.tagName.toLowerCase()")
                                if tag == "select":
                                    try:
                                        el.select_option(label=answer)
                                        filled.append(f"Screening: {lbl_text[:40]}")
                                    except Exception:
                                        pass
                                else:
                                    try:
                                        el.fill(answer)
                                        filled.append(f"Screening: {lbl_text[:40]}")
                                    except Exception:
                                        pass
                        break
        except Exception:
            pass

        # ── PAUSE — hand control to the user ──────────────────────────────────
        print("\n" + "═" * 60)
        print("  REVIEW MODE — browser is open and pre-filled.")
        print("  Please review all fields, answer any custom questions,")
        print("  and click Submit when ready.")
        print("  Press ENTER here to close the browser when done.")
        print("═" * 60 + "\n")

        input()   # wait for user to press Enter in the terminal
        browser.close()

    return {
        "ok":       True,
        "filled":   filled,
        "missing":  missing,
        "warnings": warnings,
    }
