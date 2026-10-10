from __future__ import annotations

from job_assistant.importer import parse_job_json


def test_parse_job_json_normalizes_valid_jobs():
    result = parse_job_json(
        """
        {"jobs": [{
          "source_site": "manual_import",
          "external_id": "job-1",
          "title": "Caregiver",
          "company": "Example Care",
          "city": "Lynnwood",
          "state": "WA",
          "url": "https://example.test/apply",
          "required_fields": ["name", "email", "resume"],
          "hourly_pay": "25"
        }]}
        """
    )
    assert result.errors == ()
    assert len(result.jobs) == 1
    assert result.jobs[0].hourly_pay == 25.0
    assert result.jobs[0].required_fields == ("name", "email", "resume")


def test_parse_job_json_reports_missing_required_fields():
    result = parse_job_json('[{"title":"Caregiver"}]')
    assert result.jobs == ()
    assert "company" in result.errors[0]

