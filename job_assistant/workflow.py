from __future__ import annotations

from dataclasses import dataclass


DISCOVERED = "discovered"
PREPARED = "prepared"
PENDING_REVIEW = "pending_review"
APPROVED = "approved"
OPENED_FOR_MANUAL_SUBMISSION = "opened_for_manual_submission"
SUBMITTED = "submitted"
NOT_SUBMITTED = "not_submitted"
REJECTED = "rejected"
FAILED = "failed"

VALID_TRANSITIONS = {
    DISCOVERED: {PREPARED, FAILED},
    PREPARED: {PENDING_REVIEW, FAILED},
    PENDING_REVIEW: {APPROVED, REJECTED, FAILED},
    APPROVED: {OPENED_FOR_MANUAL_SUBMISSION, REJECTED, FAILED},
    OPENED_FOR_MANUAL_SUBMISSION: {SUBMITTED, NOT_SUBMITTED, FAILED},
    SUBMITTED: set(),
    NOT_SUBMITTED: {OPENED_FOR_MANUAL_SUBMISSION, REJECTED},
    REJECTED: set(),
    FAILED: set(),
}


@dataclass(frozen=True)
class TransitionResult:
    ok: bool
    message: str


def can_transition(current: str, new: str) -> TransitionResult:
    if new in VALID_TRANSITIONS.get(current, set()):
        return TransitionResult(True, "State transition allowed.")
    return TransitionResult(False, f"Cannot move from {current} to {new}.")

