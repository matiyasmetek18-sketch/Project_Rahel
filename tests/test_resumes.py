from __future__ import annotations

from job_assistant.resumes import validate_resume_upload


def test_resume_upload_limits():
    assert validate_resume_upload("resume.pdf", 5 * 1024 * 1024)[0] is True
    assert validate_resume_upload("resume.docx", 123)[0] is True
    assert validate_resume_upload("resume.txt", 123)[0] is False
    assert validate_resume_upload("resume.pdf", 5 * 1024 * 1024 + 1)[0] is False
