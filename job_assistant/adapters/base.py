from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi

from job_assistant.models import JobPosting


class AdapterError(Exception):
    pass


class RateLimitedError(AdapterError):
    pass


class NetworkError(AdapterError):
    pass


@dataclass(frozen=True)
class FetchResult:
    jobs: tuple[JobPosting, ...]
    source_status: str


class Transport(Protocol):
    def get_json(self, url: str, headers: dict[str, str] | None = None) -> object:
        ...


class UrlLibTransport:
    def get_json(self, url: str, headers: dict[str, str] | None = None) -> object:
        request_headers = {"User-Agent": "ProjectRahel/1.0 (+local caregiver job discovery)"}
        request_headers.update(headers or {})
        request = Request(url, headers=request_headers)
        context = ssl.create_default_context(cafile=certifi.where())
        try:
            with urlopen(request, timeout=15, context=context) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 429:
                raise RateLimitedError("The job board rate limit was reached.") from exc
            raise NetworkError(f"Job board request failed with HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise NetworkError("Job board request failed or returned invalid JSON.") from exc


class JobBoardAdapter(Protocol):
    provider: str

    def fetch_jobs(self, board_identifier: str) -> FetchResult:
        ...

