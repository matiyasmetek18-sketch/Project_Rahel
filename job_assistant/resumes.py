from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import BinaryIO

ALLOWED_EXTENSIONS = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
MAX_RESUME_BYTES = 5 * 1024 * 1024
DOCX_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")


def safe_resume_name(original_filename: str) -> str:
    stem = Path(original_filename).stem
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "-", stem).strip("-") or "resume"
    return clean[:60]


def validate_resume_upload(filename: str, size_bytes: int) -> tuple[bool, str]:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return False, "Resume must be a PDF or DOCX file."
    if size_bytes > MAX_RESUME_BYTES:
        return False, "Resume must be 5 MB or smaller."
    return True, "Resume is valid."


def validate_resume_file(filename: str, size_bytes: int, stream: BinaryIO) -> tuple[bool, str]:
    ok, message = validate_resume_upload(filename, size_bytes)
    if not ok:
        return ok, message
    position = stream.tell()
    header = stream.read(8)
    stream.seek(position)
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf" and not header.startswith(b"%PDF"):
        return False, "PDF resume content does not look like a PDF file."
    if suffix == ".docx" and not header.startswith(DOCX_SIGNATURES):
        return False, "DOCX resume content does not look like a DOCX file."
    return True, "Resume is valid."


def stored_resume_path(resume_dir: Path, user_id: int, original_filename: str) -> Path:
    suffix = Path(original_filename).suffix.lower()
    return resume_dir / str(user_id) / f"{safe_resume_name(original_filename)}-{uuid.uuid4().hex}{suffix}"

