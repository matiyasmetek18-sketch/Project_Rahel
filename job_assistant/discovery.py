from __future__ import annotations

from dataclasses import dataclass

from job_assistant.adapters import GreenhouseAdapter, LeverAdapter
from job_assistant.adapters.base import AdapterError, FetchResult, JobBoardAdapter, NetworkError, RateLimitedError


@dataclass(frozen=True)
class DiscoveryResult:
    jobs_found: int
    jobs_created: int
    jobs_updated: int
    errors: tuple[str, ...]


def adapter_for(provider: str) -> JobBoardAdapter:
    if provider == "greenhouse":
        return GreenhouseAdapter()
    if provider == "lever":
        return LeverAdapter()
    if provider == "lever_eu":
        return LeverAdapter(region="eu")
    raise ValueError("Unsupported job source provider.")


__all__ = [
    "AdapterError",
    "DiscoveryResult",
    "FetchResult",
    "NetworkError",
    "RateLimitedError",
    "adapter_for",
]
