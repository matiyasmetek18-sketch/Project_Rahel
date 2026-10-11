from __future__ import annotations

import json
import re
from typing import Any

from job_assistant.adapters.base import FetchResult, Transport, UrlLibTransport
from job_assistant.adapters.html import html_to_text
from job_assistant.models import JobPosting


class LeverAdapter:
    """Read-only Lever Postings API adapter.

    Terms/docs check, October 10, 2026: Lever documents public postings under
    /v0/postings/{site} with JSON mode for published job postings. Lever's
    authenticated application and candidate APIs are not implemented here.
    """

    provider = "lever"

    def __init__(self, transport: Transport | None = None, region: str = "global") -> None:
        self.transport = transport or UrlLibTransport()
        self.region = region

    def fetch_jobs(self, board_identifier: str) -> FetchResult:
        site = board_identifier.strip()
        base = "https://api.eu.lever.co" if self.region == "eu" else "https://api.lever.co"
        url = f"{base}/v0/postings/{site}?mode=json"
        data = self.transport.get_json(url, headers={"Accept": "application/json"})
        jobs = data if isinstance(data, list) else []
        return FetchResult(tuple(normalize_lever_job(site, item) for item in jobs if isinstance(item, dict)), "Fetched from Lever.")


def normalize_lever_job(site: str, item: dict[str, Any]) -> JobPosting:
    categories = item.get("categories") if isinstance(item.get("categories"), dict) else {}
    location = str(categories.get("location") or item.get("workplaceType") or "")
    city, state = split_location(location)
    lists = item.get("lists") if isinstance(item.get("lists"), list) else []
    list_text = " ".join(str(part.get("content") or "") for part in lists if isinstance(part, dict))
    description = html_to_text(" ".join([str(item.get("description") or ""), str(item.get("additional") or ""), list_text]))
    title = str(item.get("text") or item.get("title") or "Untitled role").strip()
    url = str(item.get("applyUrl") or item.get("hostedUrl") or "")
    salary = item.get("salaryRange") if isinstance(item.get("salaryRange"), dict) else {}
    hourly_pay = parse_hourly_pay(salary, description)
    metadata = {
        "provider": "lever",
        "site": site,
        "raw_id": item.get("id"),
        "commitment": categories.get("commitment"),
        "team": categories.get("team"),
        "workplace_type": item.get("workplaceType"),
        "created_at": item.get("createdAt"),
        "hosted_url": item.get("hostedUrl"),
    }
    remote = "remote" in f"{location} {item.get('workplaceType', '')}".lower()
    return JobPosting(
        source_site=f"lever:{site}",
        external_id=str(item.get("id") or url or title),
        title=title,
        company=site,
        city=city,
        state=state,
        url=url,
        description=description,
        hourly_pay=hourly_pay,
        employment_type=str(categories.get("commitment") or ""),
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


def parse_hourly_pay(salary: dict[str, Any], text: str) -> float | None:
    interval = str(salary.get("interval") or "").lower()
    minimum = salary.get("min")
    if minimum is not None and ("hour" in interval or "wage" in interval):
        try:
            return float(minimum)
        except (TypeError, ValueError):
            pass
    match = re.search(r"\$(\d+(?:\.\d{1,2})?)\s*(?:an\s+hour|per\s+hour|/hour|/hr|hourly)", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None

