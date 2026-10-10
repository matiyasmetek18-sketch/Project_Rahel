from __future__ import annotations

from datetime import date

from job_assistant.drafting import make_cover_letter
from job_assistant.models import Credential, JobPosting, Profile
from job_assistant.rules import can_submit_application, classify_easy_apply, score_job


def test_easy_apply_only_allows_known_profile_fields():
    profile = Profile(
        full_name="Rahel Example",
        email="rahel@example.com",
        phone="555-0100",
        city="Lynnwood",
        state="WA",
        zip_code="98036",
        confirmed_resume_summary="Experienced caregiver.",
    )
    easy = JobPosting("demo", "1", "Caregiver", "Care Co", "Lynnwood", "WA", "https://example.test", required_fields=("name", "email", "phone", "resume"))
    manual = JobPosting("demo", "2", "Caregiver", "Care Co", "Lynnwood", "WA", "https://example.test", required_fields=("name", "date_of_birth"))
    assert classify_easy_apply(profile, easy).label == "easy apply"
    classified = classify_easy_apply(profile, manual)
    assert classified.label == "manual"
    assert "date_of_birth" in classified.unanswered_questions


def test_no_fabrication_in_cover_letter():
    profile = Profile(full_name="Matiyas Example", email="m@example.com")
    job = JobPosting("demo", "1", "Intern", "Tech Co", "Seattle", "WA", "https://example.test")
    letter, questions = make_cover_letter(profile, job)
    assert letter == ""
    assert "confirmed resume summary" in questions[0]


def test_expired_credentials_do_not_satisfy_requirement():
    profile = Profile("Rahel Example", "r@example.com", acceptable_cities=("Lynnwood",))
    job = JobPosting("demo", "1", "Caregiver", "Care Co", "Lynnwood", "WA", "https://example.test", required_credentials=("HCA",))
    credentials = [Credential("HCA", "WA", "2020-01-01", True)]
    result = score_job(profile, credentials, job, as_of=date(2026, 10, 10))
    assert result.value == 0
    assert result.exclusion_reason == "missing_credential"


def test_approval_gate_and_daily_limit():
    assert can_submit_application(False, 0, 5)[0] is False
    assert can_submit_application(True, 5, 5)[0] is False
    assert can_submit_application(True, 4, 5)[0] is True

