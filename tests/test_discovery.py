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
    assert result["duplicates"] == 1


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
            "Software Engineer",
            "Desk Co",
            "Tacoma",
            "WA",
            "https://example.test/weak",
            "Software product engineering",
            hourly_pay=25,
        ),
    )
    jobs = repo.list_jobs(rahel)
    assert jobs[0]["row"]["external_id"] == "good"
    assert jobs[0]["feed_score"] > jobs[1]["feed_score"]
    assert "Skills match" in jobs[0]["feed_reasons"]
    assert jobs[1]["feed_exclusion"] == "not_caregiver_role"


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
    assert result["stale"] == 1


def test_empty_successful_source_marks_existing_jobs_stale(monkeypatch, repo: Repository):
    rahel = repo.create_user("rahel", "rahel@example.com", "another-safe-password")
    repo.add_job_source(rahel, "greenhouse", "fictional-care", "Fictional Care")
    job = JobPosting("greenhouse:fictional-care", "first", "Caregiver", "Care Co", "Lynnwood", "WA", "https://example.test/first")
    monkeypatch.setattr("job_assistant.repository.adapter_for", lambda provider: FakeAdapter([job]))
    repo.fetch_jobs_from_sources(rahel)

    monkeypatch.setattr("job_assistant.repository.adapter_for", lambda provider: FakeAdapter([]))
    result = repo.fetch_jobs_from_sources(rahel)

    assert result["found"] == 0
    assert result["stale"] == 1
    assert repo.list_jobs(rahel)[0]["row"]["status"] == "stale"


def test_search_settings_influence_feed_matching(repo: Repository):
    rahel = repo.create_user("rahel", "rahel@example.com", "another-safe-password")
    repo.update_profile(rahel, full_name="Rahel Example", state="WA", minimum_hourly_pay=20)
    repo.update_search_settings(
        rahel,
        job_titles="care navigator",
        acceptable_locations="Seattle",
        minimum_pay=20,
        employment_types="Full-Time",
        search_keywords="home care, scheduling",
        remote_ok=True,
    )
    repo.upsert_job(
        rahel,
        JobPosting(
            "lever:example",
            "care-nav",
            "Care Navigator",
            "Example Health",
            "Seattle",
            "WA",
            "https://example.test/care-nav",
            "Home care scheduling for patients and caregivers.",
            hourly_pay=22,
            employment_type="Full-Time",
            remote=True,
        ),
    )

    job = repo.list_jobs(rahel)[0]

    assert job["feed_score"] >= 80
    assert "Preferred title match" in job["feed_reasons"]
    assert "Search keyword match" in job["feed_reasons"]
    assert repo.job_feed_metrics(rahel)["likely_eligible"] == 1

