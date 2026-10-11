from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from docx import Document
from pypdf import PdfReader


KNOWN_SKILLS = {
    "python",
    "javascript",
    "sql",
    "flask",
    "django",
    "react",
    "html",
    "css",
    "sqlite",
    "git",
    "caregiving",
    "hca",
    "cna",
    "first aid",
    "cpr",
    "medication",
    "transfers",
    "companionship",
    "bilingual",
    "amharic",
}

CERTIFICATION_WORDS = ("certified", "certificate", "certification", "license", "hca", "cna", "cpr", "first aid")
EDUCATION_WORDS = ("university", "college", "school", "degree", "bachelor", "associate", "computer science")
EXPERIENCE_WORDS = ("experience", "worked", "caregiver", "engineer", "developer", "intern", "assistant")


@dataclass(frozen=True)
class ResumeExtraction:
    text: str
    skills: tuple[str, ...]
    employment_history: tuple[str, ...]
    education: tuple[str, ...]
    certifications: tuple[str, ...]
    relevant_experience: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def extract_resume(path: Path) -> ResumeExtraction:
    suffix = path.suffix.lower()
    warnings: list[str] = []
    if suffix == ".pdf":
        text = extract_pdf_text(path, warnings)
    elif suffix == ".docx":
        text = extract_docx_text(path, warnings)
    else:
        text = ""
        warnings.append("Unsupported resume format for extraction.")
    return analyze_resume_text(text, tuple(warnings))


def extract_pdf_text(path: Path, warnings: list[str]) -> str:
    try:
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        warnings.append("Could not extract text from the PDF. Confirm details manually.")
        return ""


def extract_docx_text(path: Path, warnings: list[str]) -> str:
    try:
        document = Document(str(path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    except Exception:
        warnings.append("Could not extract text from the DOCX. Confirm details manually.")
        return ""


def analyze_resume_text(text: str, warnings: tuple[str, ...] = ()) -> ResumeExtraction:
    normalized = re.sub(r"\s+", " ", text).strip()
    lower = normalized.lower()
    skills = tuple(sorted(skill for skill in KNOWN_SKILLS if skill in lower))
    lines = tuple(line.strip(" -\t") for line in text.splitlines() if line.strip())
    employment = tuple(line for line in lines if any(word in line.lower() for word in EXPERIENCE_WORDS))[:8]
    education = tuple(line for line in lines if any(word in line.lower() for word in EDUCATION_WORDS))[:5]
    certifications = tuple(line for line in lines if any(word in line.lower() for word in CERTIFICATION_WORDS))[:8]
    relevant = tuple(line for line in lines if any(skill in line.lower() for skill in skills))[:8]
    return ResumeExtraction(
        text=normalized,
        skills=skills,
        employment_history=employment,
        education=education,
        certifications=certifications,
        relevant_experience=relevant,
        warnings=warnings,
    )

def suggested_summary(extraction: ResumeExtraction) -> str:
    parts = []
    if extraction.skills:
        parts.append(f"Confirmed skills to review: {', '.join(extraction.skills)}.")
    if extraction.relevant_experience:
        parts.append(extraction.relevant_experience[0])
    return " ".join(parts).strip()

