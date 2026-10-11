from __future__ import annotations

import pytest

from job_assistant.adapters.base import RateLimitedError
from job_assistant.adapters.greenhouse import GreenhouseAdapter
from job_assistant.adapters.lever import LeverAdapter


class FakeTransport:
    def __init__(self, payload=None, error: Exception | None = None):
        self.payload = payload
        self.error = error
        self.urls: list[str] = []

    def get_json(self, url: str, headers=None):
        self.urls.append(url)
        if self.error:
            raise self.error
        return self.payload


def test_greenhouse_adapter_normalizes_jobs():
    adapter = GreenhouseAdapter(
        FakeTransport(
            {
                "jobs": [
                    {
                        "id": 123,
                        "title": "In-Home Caregiver",
                        "absolute_url": "https://boards.greenhouse.io/example/jobs/123",
                        "location": {"name": "Lynnwood, WA"},
                        "content": "<p>Caregiving transfers companionship</p>",
                    }
                ]
            }
        )
    )
    result = adapter.fetch_jobs("example")
    assert result.jobs[0].source_site == "greenhouse:example"
    assert result.jobs[0].city == "Lynnwood"
    assert "Caregiving" in result.jobs[0].description


def test_lever_adapter_normalizes_jobs():
    adapter = LeverAdapter(
        FakeTransport(
            [
                {
                    "id": "abc",
                    "text": "Companion Caregiver",
                    "hostedUrl": "https://jobs.lever.co/example/abc",
                    "categories": {"location": "Everett, WA", "commitment": "Full-time"},
                    "description": "<p>Companionship care</p>",
                    "lists": [{"content": "<p>CPR helpful</p>"}],
                }
            ]
        )
    )
    result = adapter.fetch_jobs("example")
    assert result.jobs[0].source_site == "lever:example"
    assert result.jobs[0].employment_type == "Full-time"
    assert "CPR" in result.jobs[0].description


def test_adapter_rate_limit_error_is_preserved():
    adapter = GreenhouseAdapter(FakeTransport(error=RateLimitedError("rate limited")))
    with pytest.raises(RateLimitedError):
        adapter.fetch_jobs("example")

