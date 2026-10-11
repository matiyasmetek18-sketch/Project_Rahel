from __future__ import annotations

from job_assistant.models import JobPosting
from job_assistant.repository import Repository


class FakeAdapter:
    def __init__(self, jobs):
        self.jobs = jobs

    def fetch_jobs(self, board_identifier: str):
        class Result:
            source_status = "Fetched fictional jobs."

            def __init__(self, jobs):
                self.jobs = jobs

        return Result(tuple(self.jobs))


def test_fetch_jobs_from_configured_sources_is_account_scoped(monkeypatch, repo: Repository):
    rahel = repo.create_user("rahel", "rahel@example.com", "another-safe-password")
    other = repo.create_user("other", "other@example.com", "another-safe-password")
    repo.add_job_source(rahel, "greenhouse", "fictional-care", "Fictional Care")
    job = JobPosting(
        "greenhouse:fictional-care",
        "care-1",
        "In-Home Caregiver",
        "Fictional Care",
        "Lynnwood",
        "WA",
        "https://example.test/care-1",
        "Caregiving transfers companionship",
    )
    monkeypatch.setattr("job_assistant.repository.adapter_for", lambda provider: FakeAdapter([job]))
    result = repo.fetch_jobs_from_sources(rahel)
    assert result["created"] == 1
    assert len(repo.list_jobs(rahel)) == 1
    assert len(repo.list_jobs(other)) == 0
    result = repo.fetch_jobs_from_sources(rahel)
    assert result["updated"] == 1

