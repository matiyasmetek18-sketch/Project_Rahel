from __future__ import annotations

import pytest

from job_assistant.db import get_connection, utc_now
from job_assistant.models import JobPosting
from job_assistant.repository import Repository


def test_account_data_separation(repo: Repository):
    reviewer = repo.create_user("reviewer", "reviewer@example.com", "a-very-safe-password")
    rahel = repo.create_user("rahel", "rahel@example.com", "another-safe-password")
    repo.update_profile(reviewer, full_name="Reviewer", skills="audit")
    repo.update_profile(rahel, full_name="Rahel", skills="caregiving")
    assert repo.profile_for_user(reviewer).full_name == "Reviewer"
    assert repo.profile_for_user(rahel).full_name == "Rahel"
    assert repo.profile_for_user(reviewer).skills == ("audit",)
    assert repo.profile_for_user(rahel).skills == ("caregiving",)


def test_approval_must_match_account(repo: Repository):
    reviewer = repo.create_user("reviewer", "reviewer@example.com", "a-very-safe-password")
    rahel = repo.create_user("rahel", "rahel@example.com", "another-safe-password")
    job_id = repo.add_job(rahel, JobPosting("demo", "1", "Caregiver", "Care Co", "Lynnwood", "WA", "https://example.test"))
    with get_connection(repo.db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO application_drafts
            (user_id, job_id, label, score, reasons, unanswered_questions, resume_summary, cover_letter, created_at)
            VALUES (?, ?, 'manual', 50, 'reason', '', 'summary', 'letter', ?)
            """,
            (rahel, job_id, utc_now()),
        )
        draft_id = int(cur.lastrowid)
    with pytest.raises(PermissionError):
        repo.approve_draft(reviewer, draft_id, "Approve 1", 1)
