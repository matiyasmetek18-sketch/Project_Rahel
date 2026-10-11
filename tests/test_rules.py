from __future__ import annotations

from datetime import date

from job_assistant.drafting import make_cover_letter, make_form_answers
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
    profile = Profile(full_name="Rahel Example", email="rahel@example.com")
    job = JobPosting("demo", "1", "Caregiver", "Care Co", "Lynnwood", "WA", "https://example.test")
    letter, questions = make_cover_letter(profile, job)
    assert letter == ""
    assert "confirmed resume summary" in questions[0]


def test_confirmed_profile_data_populates_editable_form_answers():
    profile = Profile(
        "Rahel Example",
        "rahel@example.com",
        phone="555-0100",
        city="Lynnwood",
        state="WA",
        skills=("caregiving", "transfers"),
        availability="weekdays",
    )
    rows = [{"employer": "Fictional Care", "title": "Caregiver", "start_date": "2024-01-01", "end_date": "", "tasks": "Companionship"}]
    answers = make_form_answers(profile, rows)
    assert "Rahel Example" in answers
    assert "caregiving" in answers
    assert "Fictional Care" in answers


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


def test_caregiver_scoring_explains_missing_information_and_matches():
    profile = Profile(
        "Rahel Example",
        "rahel@example.com",
        skills=("caregiving", "transfers"),
        acceptable_cities=("Lynnwood",),
        minimum_hourly_pay=22,
        job_types=("caregiver",),
        availability="weekdays",
    )
    job = JobPosting(
        "manual_import",
        "care-1",
        "In-Home Caregiver",
        "Example Care",
        "Lynnwood",
        "WA",
        "https://example.test/apply",
        "Caregiving transfers weekdays",
        hourly_pay=25,
    )
    result = score_job(profile, [], job)
    assert result.value > 70
    assert any("City matches" in reason for reason in result.reasons)
    assert any("Skills match" in reason for reason in result.reasons)


def test_city_match_requires_state_consistency_when_state_is_known():
    profile = Profile(
        "Rahel Example",
        "rahel@example.com",
        state="WA",
        acceptable_cities=("Bellevue",),
        minimum_hourly_pay=20,
        job_types=("caregiver",),
    )
    job = JobPosting(
        "greenhouse:bayada",
        "pa-bellevue",
        "Home Caregiver",
        "Example Care",
        "Bellevue",
        "PA",
        "https://example.test/apply",
        "Home care caregiver companionship",
        hourly_pay=24,
    )
    result = score_job(profile, [], job)
    assert not any("City matches" in reason for reason in result.reasons)
    assert any("outside" in reason for reason in result.reasons)


def test_licensed_roles_require_verified_credentials_from_posting_text():
    profile = Profile("Rahel Example", "rahel@example.com", state="WA", acceptable_cities=("Everett",), minimum_hourly_pay=20)
    job = JobPosting(
        "lever:example",
        "nurse-practitioner",
        "Home-Based Acute Care Nurse Practitioner",
        "Example Health",
        "Everett",
        "WA",
        "https://example.test/apply",
        "Nurse Practitioner role delivering in-home care.",
        hourly_pay=100,
    )
    result = score_job(profile, [], job)
    assert result.value == 0
    assert result.exclusion_reason == "missing_credential"
    assert "Nurse Practitioner" in result.reasons[0]


def test_admin_titles_with_home_care_context_are_not_direct_caregiver_matches():
    profile = Profile("Rahel Example", "rahel@example.com", state="WA", acceptable_cities=("Seattle",), minimum_hourly_pay=20)
    job = JobPosting(
        "greenhouse:example",
        "counsel",
        "Manager, Senior Counsel",
        "Example Home Care",
        "Seattle",
        "WA",
        "https://example.test/apply",
        "Company provides home care and caregiver services.",
        hourly_pay=50,
    )
    result = score_job(profile, [], job, preferred_titles=("caregiver", "care navigator"), search_keywords=("home care",))
    assert result.value == 0
    assert result.exclusion_reason == "not_caregiver_role"

