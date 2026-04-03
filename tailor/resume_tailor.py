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
from typing import Optional

import anthropic
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

RESUME_PATH = os.path.join(os.path.dirname(__file__), "..", "resume.txt")
OUTPUT_DIR  = os.path.join(os.path.dirname(__file__), "..", "output")

# Sonnet for quality — resume and cover letter are high-stakes documents.
MODEL = "claude-sonnet-4-6"

TAILOR_SYSTEM = textwrap.dedent("""
    You are an expert resume writer and career coach specialising in QA / SDET / test automation roles.
    You will receive a candidate's resume and a job posting.

    Your task is to produce TWO documents, returned as a single JSON object (no markdown fences):

    {
      "tailored_resume": "<full resume text, plain text, sections separated by \\n\\n>",
      "cover_letter": "<full cover letter text, plain text>"
    }

    Rules for the TAILORED RESUME:
    - Keep ALL of the candidate's real experience — do not invent anything.
    - Reword bullet points to echo the job posting's language and keywords naturally.
    - Move the most relevant experience and skills to the top of each section.
    - Add a short 2-3 line "Target Role" summary at the very top tailored to this specific job.
    - Keep formatting simple: section headers in ALL CAPS, bullets starting with "- ".
    - Preserve the candidate's actual dates, companies, and titles exactly.
    - Always include the GitHub link (github.com/ademdeniz) in the contact header — it is a portfolio showcase.

    Rules for the COVER LETTER:
    - Address it to "Hiring Manager" (we don't know the name).
    - Opening paragraph: why this specific role at this specific company excites the candidate.
    - Middle paragraph: 2-3 most relevant achievements that directly map to the job requirements.
    - Closing paragraph: confident call to action.
    - Tone: professional but direct — not overly formal.
    - Length: 3-4 paragraphs, no filler phrases like "I am writing to express my interest".
    - Sign off: "Best regards,\\nAdem Garic"

    Return ONLY the JSON object. No explanation, no markdown.
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
    """
    Generate a tailored resume and cover letter for a given job dict.
    Returns a TailorResult with text content and file paths.
    """
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

    # Strip markdown fences if Claude adds them despite instructions
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"Could not parse JSON from tailor response:\n{raw[:500]}")

    tailored_resume = data.get("tailored_resume", "").strip()
    cover_letter    = data.get("cover_letter", "").strip()

    # ── Save files ────────────────────────────────────────────────────────────
    slug = _slug(title, company)
    out_dir = os.path.join(OUTPUT_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)

    resume_path = os.path.join(out_dir, "resume.docx")
    cl_path     = os.path.join(out_dir, "cover_letter.docx")

    _write_resume_docx(tailored_resume, title, company, resume_path)
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

def _set_font(run, size_pt: int = 11, bold: bool = False, color: Optional[tuple] = None):
    run.font.name = "Calibri"
    run.font.size = Pt(size_pt)
    run.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)


def _write_resume_docx(text: str, title: str, company: str, path: str):
    doc = Document()

    # Narrow margins
    for section in doc.sections:
        section.top_margin    = Pt(36)
        section.bottom_margin = Pt(36)
        section.left_margin   = Pt(54)
        section.right_margin  = Pt(54)

    HEADING_COLOR = (30, 64, 175)   # blue

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            doc.add_paragraph()
            continue

        # ALL-CAPS line = section header
        if stripped.isupper() and len(stripped) > 2:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(6)
            run = p.add_run(stripped)
            _set_font(run, size_pt=11, bold=True, color=HEADING_COLOR)
            # Underline via border trick
            p.paragraph_format.border_bottom = None
            continue

        # Bullet line
        if stripped.startswith("- "):
            p = doc.add_paragraph(style="List Bullet")
            run = p.add_run(stripped[2:])
            _set_font(run, size_pt=10)
            continue

        # Regular line (name, contact, job title/company/date combos)
        p = doc.add_paragraph()
        run = p.add_run(stripped)
        # Name line (first non-empty line) — make it bigger
        if path.endswith("resume.docx") and doc.paragraphs and len(doc.paragraphs) <= 2:
            _set_font(run, size_pt=14, bold=True)
        else:
            _set_font(run, size_pt=10)

    doc.save(path)


def _write_cover_letter_docx(text: str, title: str, company: str, path: str):
    doc = Document()

    for section in doc.sections:
        section.top_margin    = Pt(54)
        section.bottom_margin = Pt(54)
        section.left_margin   = Pt(72)
        section.right_margin  = Pt(72)

    # Header: role + company
    header_p = doc.add_paragraph()
    header_r = header_p.add_run(f"Re: {title} — {company}")
    _set_font(header_r, size_pt=11, bold=True)
    doc.add_paragraph()

    for para in text.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(10)
        run = p.add_run(para)
        _set_font(run, size_pt=11)

    doc.save(path)
