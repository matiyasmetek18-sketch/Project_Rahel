from __future__ import annotations

import json
import re
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
    company = str(item.get("company_name") or board_token).strip()
    absolute_url = str(item.get("absolute_url") or "")
    metadata_items = item.get("metadata") if isinstance(item.get("metadata"), list) else []
    metadata_values = {
        str(entry.get("name")): entry.get("value")
        for entry in metadata_items
        if isinstance(entry, dict) and entry.get("name")
    }
    employment_type = str(metadata_values.get("Employment Type") or "")
    hourly_pay = parse_hourly_pay(description)
    metadata = {
        "provider": "greenhouse",
        "board_token": board_token,
        "raw_id": item.get("id"),
        "location": location_name,
        "first_published": item.get("first_published"),
        "updated_at": item.get("updated_at"),
        "employment_type": employment_type,
        "job_category": metadata_values.get("Job Category"),
    }
    remote_value = metadata_values.get("Remote")
    remote = bool(remote_value) if remote_value is not None else "remote" in location_name.lower()
    return JobPosting(
        source_site=f"greenhouse:{board_token}",
        external_id=str(item.get("id") or absolute_url or title),
        title=title,
        company=company,
        city=city,
        state=state,
        url=absolute_url,
        description=description,
        hourly_pay=hourly_pay,
        employment_type=employment_type,
        remote=remote,
        source_metadata=json.dumps(metadata, sort_keys=True),
    )


def split_location(value: str) -> tuple[str, str]:
    match = re.search(r"^\s*(.+?),\s*([A-Z]{2})(?:\s+\d|\s*\||\s*$)", value)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return value.strip(), ""


def parse_hourly_pay(text: str) -> float | None:
    hourly_patterns = [
        r"\$(\d+(?:\.\d{1,2})?)\s*(?:-|to|–|—)\s*\$?\d+(?:\.\d{1,2})?\s*(?:an\s+hour|per\s+hour|/hour|/hr|hourly)",
        r"\$(\d+(?:\.\d{1,2})?)\s*(?:an\s+hour|per\s+hour|/hour|/hr|hourly)",
    ]
    for pattern in hourly_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None

