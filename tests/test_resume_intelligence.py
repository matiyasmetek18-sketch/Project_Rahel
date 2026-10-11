from __future__ import annotations

from docx import Document

from job_assistant.resume_intelligence import analyze_resume_text, extract_resume


def test_analyze_resume_text_extracts_candidate_information_without_verifying_it():
    extraction = analyze_resume_text(
        """
        Rahel Example
        Experienced caregiver providing transfers and companionship.
        CPR certification and First Aid certificate.
        Community College caregiver training.
        """
    )
    assert "caregiving" in extraction.skills or "transfers" in extraction.skills
    assert extraction.certifications
    assert extraction.education


def test_extract_docx_resume(tmp_path):
    path = tmp_path / "resume.docx"
    document = Document()
    document.add_paragraph("Experienced caregiver with CPR and transfers experience.")
    document.save(path)
    extraction = extract_resume(path)
    assert "caregiver" in extraction.text.lower()
    assert "cpr" in extraction.skills

