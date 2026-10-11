from __future__ import annotations

import pytest

from job_assistant.db import get_connection
from job_assistant.models import JobPosting
from job_assistant.repository import Repository


def make_prepared_draft(repo: Repository, user_id: int) -> int:
    repo.update_profile(
        user_id,
        full_name="Rahel Example",
        phone="555-0100",
        city="Lynnwood",
        state="WA",
        zip_code="98036",
        acceptable_cities="Lynnwood",
        confirmed_resume_summary="Experienced caregiver with confirmed resume summary.",
    )
    job_id, _ = repo.upsert_job(
        user_id,
        JobPosting(
            "manual_import",
            "job-1",
            "Caregiver",
            "Example Care",
            "Lynnwood",
            "WA",
            "https://example.test/apply",
            "caregiver companionship",
            ("name", "email", "phone", "resume"),
            (),
        ),
    )
    return repo.prepare_job(user_id, job_id)


def test_job_deduplication_is_per_account(repo: Repository):
    matiyas = repo.create_user("matiyas", "matiyas@example.com", "a-very-safe-password")
    rahel = repo.create_user("rahel", "rahel@example.com", "another-safe-password")
    job = JobPosting("manual_import", "same-id", "Role", "Company", "Seattle", "WA", "https://example.test")
    assert repo.upsert_job(matiyas, job) == (1, True)
    assert repo.upsert_job(matiyas, job) == (1, False)
    other_id, created = repo.upsert_job(rahel, job)
    assert created is True
    assert other_id != 1


def test_review_state_machine_manual_submission(repo: Repository):
    user_id = repo.create_user("rahel", "rahel@example.com", "another-safe-password")
    draft_id = make_prepared_draft(repo, user_id)
    with pytest.raises(ValueError):
        repo.open_for_manual_submission(user_id, draft_id)
    repo.approve_draft(user_id, draft_id, "Approved 1 application", 1)
    assert repo.open_for_manual_submission(user_id, draft_id) == "https://example.test/apply"
    repo.confirm_manual_submission(user_id, draft_id, True, "Submitted by user.")
    assert repo.get_draft(user_id, draft_id)["status"] == "submitted"


def test_approval_requires_required_questions_to_be_answered(repo: Repository):
    user_id = repo.create_user("rahel", "rahel@example.com", "another-safe-password")
    repo.update_profile(
        user_id,
        full_name="Rahel Example",
        phone="555-0100",
        city="Lynnwood",
        state="WA",
        zip_code="98036",
        confirmed_resume_summary="Experienced caregiver.",
    )
    job_id, _ = repo.upsert_job(
        user_id,
        JobPosting(
            "manual_import",
            "job-missing",
            "Caregiver",
            "Example Care",
            "Lynnwood",
            "WA",
            "https://example.test/apply",
            "caregiver",
            ("name", "email", "phone", "resume", "desired_shift"),
            (),
        ),
    )
    draft_id = repo.prepare_job(user_id, job_id)
    with pytest.raises(ValueError, match="required questions"):
        repo.approve_draft(user_id, draft_id, "Approved 1 application", 1)
    repo.update_draft_text(user_id, draft_id, "Experienced caregiver.", "Letter", "desired_shift: days")
    repo.approve_draft(user_id, draft_id, "Approved 1 application", 1)
    assert repo.get_draft(user_id, draft_id)["status"] == "approved"


def test_pause_all_blocks_manual_open(repo: Repository):
    user_id = repo.create_user("rahel", "rahel@example.com", "another-safe-password")
    draft_id = make_prepared_draft(repo, user_id)
    repo.approve_draft(user_id, draft_id, "Approved 1 application", 1)
    repo.update_account_settings(user_id, 5, True, True, True)
    with pytest.raises(ValueError, match="Pause-all"):
        repo.open_for_manual_submission(user_id, draft_id)


def test_daily_limit_blocks_manual_open(repo: Repository):
    user_id = repo.create_user("rahel", "rahel@example.com", "another-safe-password")
    draft_id = make_prepared_draft(repo, user_id)
    repo.approve_draft(user_id, draft_id, "Approved 1 application", 1)
    repo.update_account_settings(user_id, 1, False, True, True)
    with get_connection(repo.db_path) as conn:
        conn.execute(
            """
            INSERT INTO application_events (user_id, draft_id, source_site, event_type, message, created_at)
            VALUES (?, ?, 'manual_import', 'submitted', 'Existing submission', datetime('now'))
            """,
            (user_id, draft_id),
        )
    with pytest.raises(ValueError, match="daily limit"):
        repo.open_for_manual_submission(user_id, draft_id)

