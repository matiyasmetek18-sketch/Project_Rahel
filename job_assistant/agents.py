from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDecision:
    allowed: bool
    reason: str


class DiscoveryAgent:
    """Finds caregiver postings through configured read-only job-board APIs."""


class MatchingAgent:
    """Uses deterministic scoring to compare postings with Rahel's verified profile."""


class ApplicationAgent:
    """Prepares truthful drafts from confirmed profile data only."""


class BrowserAgent:
    """Reserved for future browser-assisted workflows.

    This class intentionally has no automation implementation yet. Milestone 3A
    stops before browser automation and automatic submission.
    """

    def may_submit(self) -> AgentDecision:
        return AgentDecision(False, "Browser submission is not implemented in Milestone 3A.")


class VerificationAgent:
    """Checks that required data, approval, and site permissions exist before any future submission."""


class TrackingAgent:
    """Records application state changes and audit history through repository methods."""

