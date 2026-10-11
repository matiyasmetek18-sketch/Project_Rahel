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


def test_job_feed_ranks_unprepared_jobs_with_explanations(repo: Repository):
    rahel = repo.create_user("rahel", "rahel@example.com", "another-safe-password")
    repo.update_profile(
        rahel,
        full_name="Rahel Example",
        skills="caregiving, transfers",
        acceptable_cities="Lynnwood",
        minimum_hourly_pay=22,
        job_types="caregiver",
        confirmed_resume_summary="Experienced caregiver.",
    )
    repo.upsert_job(
        rahel,
        JobPosting(
            "manual_import",
            "good",
            "In-Home Caregiver",
            "Good Care",
            "Lynnwood",
            "WA",
            "https://example.test/good",
            "Caregiving transfers companionship",
            hourly_pay=25,
        ),
    )
    repo.upsert_job(
        rahel,
        JobPosting(
            "manual_import",
            "weak",
            "Office Assistant",
            "Desk Co",
            "Tacoma",
            "WA",
            "https://example.test/weak",
            "Office scheduling",
            hourly_pay=18,
        ),
    )
    jobs = repo.list_jobs(rahel)
    assert jobs[0]["row"]["external_id"] == "good"
    assert jobs[0]["feed_score"] > jobs[1]["feed_score"]
    assert "Skills match" in jobs[0]["feed_reasons"]


def test_fetch_marks_missing_source_jobs_stale(monkeypatch, repo: Repository):
    rahel = repo.create_user("rahel", "rahel@example.com", "another-safe-password")
    repo.add_job_source(rahel, "greenhouse", "fictional-care", "Fictional Care")
    first = JobPosting("greenhouse:fictional-care", "first", "Caregiver", "Care Co", "Lynnwood", "WA", "https://example.test/first")
    second = JobPosting("greenhouse:fictional-care", "second", "Caregiver", "Care Co", "Lynnwood", "WA", "https://example.test/second")
    monkeypatch.setattr("job_assistant.repository.adapter_for", lambda provider: FakeAdapter([first, second]))
    repo.fetch_jobs_from_sources(rahel)
    monkeypatch.setattr("job_assistant.repository.adapter_for", lambda provider: FakeAdapter([first]))
    result = repo.fetch_jobs_from_sources(rahel)
    assert result["updated"] == 2
    jobs = {item["row"]["external_id"]: item["row"] for item in repo.list_jobs(rahel)}
    assert jobs["second"]["status"] == "stale"
    assert "No longer returned" in jobs["second"]["exclusion_reason"]

