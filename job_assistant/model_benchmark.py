from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    posting: str
    expected_requirements: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkResult:
    model_name: str
    accuracy: float
    latency_ms: int
    cost_per_1k: float
    notes: str


class ModelCandidate(Protocol):
    name: str
    cost_per_1k: float

    def extract_requirements(self, posting: str) -> tuple[str, ...]:
        ...


FICTIONAL_BENCHMARK = (
    BenchmarkCase(
        "caregiver_basic",
        "In-home caregiver. Requires CPR, weekend availability, transfer assistance, and reliable transportation.",
        ("cpr", "weekend availability", "transfer assistance", "reliable transportation"),
    ),
    BenchmarkCase(
        "facility_care",
        "Assisted living caregiver. HCA license preferred. Must support companionship and medication reminders.",
        ("hca license preferred", "companionship", "medication reminders"),
    ),
)


def score_model(candidate: ModelCandidate, cases: tuple[BenchmarkCase, ...] = FICTIONAL_BENCHMARK) -> BenchmarkResult:
    total = 0
    matched = 0
    for case in cases:
        predicted = {item.lower().strip() for item in candidate.extract_requirements(case.posting)}
        expected = {item.lower().strip() for item in case.expected_requirements}
        total += len(expected)
        matched += len(expected & predicted)
    accuracy = matched / total if total else 0.0
    return BenchmarkResult(candidate.name, accuracy, 0, candidate.cost_per_1k, "Fictional offline benchmark.")

