from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .models import JobPosting


@dataclass(frozen=True)
class ImportResult:
    jobs: tuple[JobPosting, ...]
    errors: tuple[str, ...]


def parse_job_json(payload: str, default_source: str = "manual_import") -> ImportResult:
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        return ImportResult((), (f"Invalid JSON: {exc.msg}.",))

    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict) and isinstance(raw.get("jobs"), list):
        items = raw["jobs"]
    elif isinstance(raw, dict):
        return ImportResult((), ("JSON object must include a jobs list.",))
    else:
        return ImportResult((), ("JSON must be a list of jobs or an object with a jobs list.",))
    if not isinstance(items, list):
        return ImportResult((), ("JSON must be a list of jobs or an object with a jobs list.",))

    jobs: list[JobPosting] = []
    errors: list[str] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"Job {index} must be an object.")
            continue
        missing = [field for field in ("title", "company", "url") if not str(item.get(field, "")).strip()]
        if missing:
            errors.append(f"Job {index} is missing: {', '.join(missing)}.")
            continue
        url = clean(item.get("url"))
        if not is_http_url(url):
            errors.append(f"Job {index} url must start with http:// or https://.")
            continue
        source_site = clean(item.get("source_site")) or default_source
        external_id = clean(item.get("external_id")) or f"{source_site}:{url}"
        jobs.append(
            JobPosting(
                source_site=source_site,
                external_id=external_id,
                title=clean(item.get("title")),
                company=clean(item.get("company")),
                city=clean(item.get("city")),
                state=clean(item.get("state")),
                url=url,
                description=clean(item.get("description")),
                required_fields=tuple_list(item.get("required_fields")),
                required_credentials=tuple_list(item.get("required_credentials")),
                hourly_pay=number_or_none(item.get("hourly_pay")),
            )
        )
    return ImportResult(tuple(jobs), tuple(errors))


def clean(value: Any) -> str:
    return str(value or "").strip()


def tuple_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, list):
        return tuple(str(part).strip() for part in value if str(part).strip())
    return ()


def number_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
