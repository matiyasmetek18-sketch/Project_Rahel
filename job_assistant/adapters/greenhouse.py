from __future__ import annotations

import json
from typing import Any

from job_assistant.adapters.base import FetchResult, Transport, UrlLibTransport
from job_assistant.adapters.html import html_to_text
from job_assistant.models import JobPosting


class GreenhouseAdapter:
    """Read-only Greenhouse Job Board API adapter.

    Terms/docs check, October 10, 2026: Greenhouse documents public GET
    endpoints for job board data without authentication. The application POST
    endpoint requires Basic Auth and is intentionally not implemented here.
    Greenhouse's MSA says API usage may be subject to usage limits/rate limits,
    so callers must handle 429s and avoid aggressive polling.
    """

    provider = "greenhouse"

    def __init__(self, transport: Transport | None = None) -> None:
        self.transport = transport or UrlLibTransport()

    def fetch_jobs(self, board_identifier: str) -> FetchResult:
        token = board_identifier.strip()
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        data = self.transport.get_json(url, headers={"Accept": "application/json"})
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
        return FetchResult(tuple(normalize_greenhouse_job(token, item) for item in jobs if isinstance(item, dict)), "Fetched from Greenhouse.")


def normalize_greenhouse_job(board_token: str, item: dict[str, Any]) -> JobPosting:
    location = item.get("location") or {}
    location_name = location.get("name", "") if isinstance(location, dict) else ""
    city, state = split_location(location_name)
    description = html_to_text(str(item.get("content") or ""))
    title = str(item.get("title") or "Untitled role").strip()
    company = board_token
    absolute_url = str(item.get("absolute_url") or "")
    metadata = {
        "provider": "greenhouse",
        "board_token": board_token,
        "raw_id": item.get("id"),
        "location": location_name,
        "updated_at": item.get("updated_at"),
    }
    remote = "remote" in f"{location_name} {description}".lower()
    return JobPosting(
        source_site=f"greenhouse:{board_token}",
        external_id=str(item.get("id") or absolute_url or title),
        title=title,
        company=company,
        city=city,
        state=state,
        url=absolute_url,
        description=description,
        hourly_pay=None,
        employment_type="",
        remote=remote,
        source_metadata=json.dumps(metadata, sort_keys=True),
    )


def split_location(value: str) -> tuple[str, str]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return value.strip(), ""

