"""
Resume Tailor + Cover Letter Generator using Claude API.

Given a job posting and the candidate's resume, generates:
  1. A tailored resume — same content, bullets reworded/reordered to mirror
     the job's language and priorities.
  2. A professional cover letter — specific to the role and company, not generic.

Both are saved as .docx files in output/<slug>/.
"""

import json
import os
import re
import textwrap
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import anthropic
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

RESUME_PATH = os.path.join(os.path.dirname(__file__), "..", "resume.txt")
OUTPUT_DIR  = os.path.join(os.path.dirname(__file__), "..", "output")

MODEL = "claude-sonnet-4-6"

TAILOR_SYSTEM = textwrap.dedent("""
    You are an expert resume writer and career coach specialising in QA / SDET / test automation roles.
    You will receive a candidate's resume and a job posting.

    Your task is to produce TWO documents, returned as a single JSON object (no markdown fences):

    {
      "tailored_resume": "<full resume text, structured as described below>",
      "cover_letter": "<full cover letter text, plain paragraphs separated by blank lines>"
    }

    TAILORED RESUME structure (use exactly these markers):
    Line 1: Candidate full name (no pronouns)
    Line 2: Contact line (city · email · LinkedIn · GitHub)
    Line 3: blank
    <<<SECTION: PROFESSIONAL SUMMARY>>>
    2-3 sentences tailored to THIS specific job — connect the candidate's background directly to the role's priorities.
    <<<SECTION: CORE SKILLS>>>
    Skill groups as "Category: skill1, skill2, skill3" — one per line, reordered so most relevant to this job comes first.
    <<<SECTION: PROFESSIONAL EXPERIENCE>>>
    For each role:
    TITLE | COMPANY | DATE RANGE
    - bullet (start with strong action verb, mirror job posting language)
    - bullet
    (blank line between roles)
    <<<SECTION: EDUCATION>>>
    Degree — Institution | Year
    <<<SECTION: CERTIFICATIONS>>>
    - Cert name — Issuer (Year)
    <<<SECTION: LANGUAGES>>>
    Languages line

    Rules:
    - Keep ALL real experience — do not invent anything.
    - Reword bullets to echo the job posting's language naturally.
    - Prioritise the most relevant bullets for this job.
    - Preserve actual dates, companies, and titles exactly.
    - Always include github.com/ademdeniz in the contact line.

    COVER LETTER rules:
    - NO "Dear Hiring Manager" opener on its own line — weave it into the first sentence naturally OR skip it.
    - Opening paragraph: lead with a strong hook connecting the candidate's background to this specific role/company.
    - Middle 1-2 paragraphs: 2-3 concrete achievements that map directly to the job requirements.
    - Closing paragraph: confident, specific call to action.
    - Tone: direct and confident, not stiff or generic. No filler phrases.
    - End with: "Best regards,\n\nAdem Garic\nademdenizgaric@gmail.com | linkedin.com/in/adem-garic-sdet-qa"
    - Length: 3-4 paragraphs total.

    Return ONLY the JSON object. No explanation, no markdown fences.
""").strip()


@dataclass
class TailorResult:
    tailored_resume: str
    cover_letter: str
    output_dir: str
    resume_path: str
    cover_letter_path: str


def _load_resume() -> str:
    if not os.path.exists(RESUME_PATH):
        raise FileNotFoundError(f"resume.txt not found at {RESUME_PATH}")
    with open(RESUME_PATH, encoding="utf-8") as f:
        return f.read().strip()


def _slug(title: str, company: str) -> str:
    raw = f"{title}_{company}"
    return re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")[:60]


def tailor_job(job: dict, resume_text: Optional[str] = None) -> TailorResult:
    if resume_text is None:
        resume_text = _load_resume()

    title       = job.get("title", "")
    company     = job.get("company", "")
    description = job.get("description", "") or ""

    if not description.strip():
        raise ValueError(f"Job {job.get('id')} has no description — cannot tailor. Fetch the description first.")

    client = anthropic.Anthropic()

    user_msg = textwrap.dedent(f"""
        ## Candidate Resume
        {resume_text}

        ## Job Posting
        Title:   {title}
        Company: {company}

        {description[:4000]}
    """).strip()

    print(f"[Tailor] Calling Claude {MODEL} for: {title} @ {company}…")
    message = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=TAILOR_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = message.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
        else:
            raise ValueError(f"Could not parse JSON from tailor response:\n{raw[:500]}")

    tailored_resume = data.get("tailored_resume", "").strip()
    cover_letter    = data.get("cover_letter", "").strip()

    slug    = _slug(title, company)
    out_dir = os.path.join(OUTPUT_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)

    resume_path = os.path.join(out_dir, "resume.docx")
    cl_path     = os.path.join(out_dir, "cover_letter.docx")

    _write_resume_docx(tailored_resume, resume_path)
    _write_cover_letter_docx(cover_letter, title, company, cl_path)

    print(f"[Tailor] Saved to {out_dir}/")
    return TailorResult(
        tailored_resume=tailored_resume,
        cover_letter=cover_letter,
        output_dir=out_dir,
        resume_path=resume_path,
        cover_letter_path=cl_path,
    )


# ── DOCX helpers ──────────────────────────────────────────────────────────────

DARK      = RGBColor(0x1e, 0x29, 0x3b)   # slate-800 — body text
ACCENT    = RGBColor(0x1d, 0x4e, 0xd8)   # blue-700  — section headers
MUTED     = RGBColor(0x64, 0x74, 0x8b)   # slate-500 — contact / dates
FONT_NAME = "Calibri"


def _font(run, size: float, bold=False, italic=False, color: RGBColor = None):
    run.font.name   = FONT_NAME
    run.font.size   = Pt(size)
    run.bold        = bold
    run.italic      = italic
    if color:
        run.font.color.rgb = color


def _para_fmt(p, space_before=0, space_after=0, line_spacing=None):
    fmt = p.paragraph_format
    fmt.space_before = Pt(space_before)
    fmt.space_after  = Pt(space_after)
    if line_spacing:
        fmt.line_spacing = Pt(line_spacing)


def _add_hrule(doc):
    """Add a thin horizontal rule via paragraph border."""
    p = doc.add_paragraph()
    _para_fmt(p, space_before=2, space_after=2)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "1d4ed8")   # same blue as ACCENT
    pBdr.append(bottom)
    pPr.append(pBdr)


def _write_resume_docx(text: str, path: str):
    doc = Document()

    # ── Margins ───────────────────────────────────────────────────────────────
    for sec in doc.sections:
        sec.top_margin    = Inches(0.55)
        sec.bottom_margin = Inches(0.55)
        sec.left_margin   = Inches(0.75)
        sec.right_margin  = Inches(0.75)

    # Remove default style spacing
    style = doc.styles["Normal"]
    style.font.name = FONT_NAME
    style.font.size = Pt(10)

    lines = text.splitlines()
    i = 0
    name_written = False

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        # ── Section marker ────────────────────────────────────────────────────
        m = re.match(r"<<<SECTION:\s*(.+?)>>>", stripped)
        if m:
            _add_hrule(doc)
            p = doc.add_paragraph()
            _para_fmt(p, space_before=4, space_after=2)
            run = p.add_run(m.group(1).upper())
            _font(run, size=9.5, bold=True, color=ACCENT)
            i += 1
            continue

        # ── Blank line ────────────────────────────────────────────────────────
        if not stripped:
            if not name_written:
                i += 1
                continue
            doc.add_paragraph()
            i += 1
            continue

        # ── Name (first non-empty line) ───────────────────────────────────────
        if not name_written:
            p = doc.add_paragraph()
            _para_fmt(p, space_after=2)
            run = p.add_run(stripped)
            _font(run, size=20, bold=True, color=DARK)
            name_written = True
            i += 1
            continue

        # ── Contact line (contains · or @ or linkedin or github) ─────────────
        contact_signals = ("·", "@", "linkedin", "github", "linkedin.com", "github.com")
        if any(s in stripped.lower() for s in contact_signals) and i < 4:
            p = doc.add_paragraph()
            _para_fmt(p, space_after=4)
            run = p.add_run(stripped)
            _font(run, size=9, color=MUTED)
            i += 1
            continue

        # ── Experience role header: TITLE | COMPANY | DATE ───────────────────
        if "|" in stripped and stripped.count("|") >= 1:
            parts = [p.strip() for p in stripped.split("|")]
            p = doc.add_paragraph()
            _para_fmt(p, space_before=6, space_after=1)
            # Title bold, company and date muted
            r_title = p.add_run(parts[0])
            _font(r_title, size=10, bold=True, color=DARK)
            if len(parts) >= 2:
                r_sep = p.add_run("  |  ")
                _font(r_sep, size=10, color=MUTED)
                r_co = p.add_run(parts[1])
                _font(r_co, size=10, color=MUTED)
            if len(parts) >= 3:
                r_sep2 = p.add_run("  |  ")
                _font(r_sep2, size=10, color=MUTED)
                r_date = p.add_run(parts[2])
                _font(r_date, size=10, italic=True, color=MUTED)
            i += 1
            continue

        # ── Bullet ────────────────────────────────────────────────────────────
        if stripped.startswith("- "):
            p = doc.add_paragraph(style="List Bullet")
            _para_fmt(p, space_before=1, space_after=1)
            run = p.add_run(stripped[2:])
            _font(run, size=9.5, color=DARK)
            i += 1
            continue

        # ── Everything else (education line, cert, language) ──────────────────
        p = doc.add_paragraph()
        _para_fmt(p, space_before=1, space_after=1)
        run = p.add_run(stripped)
        _font(run, size=9.5, color=DARK)
        i += 1

    doc.save(path)


def _write_cover_letter_docx(text: str, title: str, company: str, path: str):
    doc = Document()

    for sec in doc.sections:
        sec.top_margin    = Inches(1.0)
        sec.bottom_margin = Inches(1.0)
        sec.left_margin   = Inches(1.1)
        sec.right_margin  = Inches(1.1)

    style = doc.styles["Normal"]
    style.font.name = FONT_NAME
    style.font.size = Pt(11)

    # ── Letterhead ────────────────────────────────────────────────────────────
    p_name = doc.add_paragraph()
    r = p_name.add_run("Adem Garic")
    _font(r, size=16, bold=True, color=DARK)

    p_contact = doc.add_paragraph()
    r2 = p_contact.add_run(
        "ademdenizgaric@gmail.com  ·  linkedin.com/in/adem-garic-sdet-qa  ·  github.com/ademdeniz"
    )
    _font(r2, size=9, color=MUTED)
    _para_fmt(p_contact, space_after=4)

    _add_hrule(doc)

    # Date
    p_date = doc.add_paragraph()
    r_date = p_date.add_run(datetime.now().strftime("%B %d, %Y"))
    _font(r_date, size=10, color=MUTED)
    _para_fmt(p_date, space_before=8, space_after=2)

    # Role line
    p_role = doc.add_paragraph()
    r_role = p_role.add_run(f"Re: {title}  —  {company}")
    _font(r_role, size=10, bold=True, color=ACCENT)
    _para_fmt(p_role, space_after=12)

    # ── Body paragraphs ───────────────────────────────────────────────────────
    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        # Sign-off block — preserve line breaks
        if "Best regards" in para or "Adem Garic" in para:
            for line in para.splitlines():
                p = doc.add_paragraph()
                run = p.add_run(line.strip())
                bold = "Best regards" in line or line.strip() == "Adem Garic"
                _font(run, size=11, bold=bold, color=DARK)
                _para_fmt(p, space_before=0, space_after=1)
            continue

        p = doc.add_paragraph()
        run = p.add_run(para)
        _font(run, size=11, color=DARK)
        _para_fmt(p, space_before=0, space_after=10, line_spacing=14)

    doc.save(path)
