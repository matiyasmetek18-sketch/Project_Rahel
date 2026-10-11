from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
        request = Request(url, headers=headers or {})
        try:
            with urlopen(request, timeout=15) as response:
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

