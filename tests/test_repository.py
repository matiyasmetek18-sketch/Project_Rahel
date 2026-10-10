from __future__ import annotations

import pytest

from job_assistant.db import get_connection, utc_now
from job_assistant.models import JobPosting
from job_assistant.repository import Repository


def test_account_data_separation(repo: Repository):
    matiyas = repo.create_user("matiyas", "matiyas@example.com", "a-very-safe-password")
    rahel = repo.create_user("rahel", "rahel@example.com", "another-safe-password")
    repo.update_profile(matiyas, full_name="Matiyas", skills="python")
    repo.update_profile(rahel, full_name="Rahel", skills="caregiving")
    assert repo.profile_for_user(matiyas).full_name == "Matiyas"
    assert repo.profile_for_user(rahel).full_name == "Rahel"
    assert repo.profile_for_user(matiyas).skills == ("python",)
    assert repo.profile_for_user(rahel).skills == ("caregiving",)


def test_approval_must_match_account(repo: Repository):
    matiyas = repo.create_user("matiyas", "matiyas@example.com", "a-very-safe-password")
    rahel = repo.create_user("rahel", "rahel@example.com", "another-safe-password")
    job_id = repo.add_job(matiyas, JobPosting("demo", "1", "Intern", "Tech Co", "Seattle", "WA", "https://example.test"))
    with get_connection(repo.db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO application_drafts
            (user_id, job_id, label, score, reasons, unanswered_questions, resume_summary, cover_letter, created_at)
            VALUES (?, ?, 'manual', 50, 'reason', '', 'summary', 'letter', ?)
            """,
            (matiyas, job_id, utc_now()),
        )
        draft_id = int(cur.lastrowid)
    with pytest.raises(PermissionError):
        repo.approve_draft(rahel, draft_id, "Approve 1", 1)
