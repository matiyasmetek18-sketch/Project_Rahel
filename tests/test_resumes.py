from __future__ import annotations

from io import BytesIO

from job_assistant.resumes import validate_resume_file, validate_resume_upload


def test_resume_upload_limits():
    assert validate_resume_upload("resume.pdf", 5 * 1024 * 1024)[0] is True
    assert validate_resume_upload("resume.docx", 123)[0] is True
    assert validate_resume_upload("resume.txt", 123)[0] is False
    assert validate_resume_upload("resume.pdf", 5 * 1024 * 1024 + 1)[0] is False


def test_resume_file_signature_must_match_extension():
    assert validate_resume_file("resume.pdf", 20, BytesIO(b"not actually a pdf"))[0] is False
    assert validate_resume_file("resume.pdf", 20, BytesIO(b"%PDF-1.7\nfictional"))[0] is True
    assert validate_resume_file("resume.docx", 20, BytesIO(b"not a docx"))[0] is False
    assert validate_resume_file("resume.docx", 20, BytesIO(b"PK\x03\x04fictional"))[0] is True
