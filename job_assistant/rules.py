from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date

from .models import Credential, JobPosting, Profile

SENSITIVE_FIELDS = {
    "ssn",
    "date_of_birth",
    "dob",
    "bank_account",
    "background_check",
    "health_history",
    "demographic",
    "race",
    "gender",
    "disability",
    "veteran_status",
}

PROFILE_FIELDS = {"name", "email", "phone", "city", "state", "zip", "resume"}


@dataclass(frozen=True)
class Classification:
    label: str
    unanswered_questions: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Score:
    value: int
    reasons: tuple[str, ...]
    exclusion_reason: str | None = None


def classify_easy_apply(profile: Profile, job: JobPosting) -> Classification:
    answers = profile.answers()
    unanswered: list[str] = []
    reasons: list[str] = []

    for field in job.required_fields:
        normalized = field.strip().lower()
        if normalized in SENSITIVE_FIELDS:
            unanswered.append(field)
            reasons.append(f"{field} must be answered by the user.")
        elif normalized not in PROFILE_FIELDS or normalized not in answers:
            unanswered.append(field)

    if unanswered:
        return Classification("manual", tuple(unanswered), tuple(reasons or ["The form needs information not stored in the profile."]))
    return Classification("easy apply", (), ("The form only needs stored basic information and a resume.",))


def score_job(profile: Profile, credentials: list[Credential], job: JobPosting, as_of: date | None = None) -> Score:
    score = 40
    reasons: list[str] = []
    credential_names = {c.name.lower() for c in credentials if c.is_current(as_of)}

    if job.city and job.city.lower() in {c.lower() for c in profile.acceptable_cities}:
        score += 20
        reasons.append("City matches the user's acceptable cities.")
    elif profile.acceptable_cities:
        score -= 15
        reasons.append("City is outside the user's preferred cities.")

    if job.hourly_pay is not None and profile.minimum_hourly_pay is not None:
        if job.hourly_pay >= profile.minimum_hourly_pay:
            score += 15
            reasons.append("Pay meets the user's minimum.")
        else:
            return Score(0, ("Pay is below the user's minimum.",), "pay_below_minimum")

    missing_credentials = [required for required in job.required_credentials if required.lower() not in credential_names]
    if missing_credentials:
        return Score(0, (f"Missing current verified credential: {', '.join(missing_credentials)}.",), "missing_credential")

    words = Counter(job.description.lower().replace(",", " ").split())
    matched_skills = [skill for skill in profile.skills if skill.lower() in words]
    if matched_skills:
        score += min(25, len(matched_skills) * 5)
        reasons.append(f"Skills match: {', '.join(matched_skills)}.")

    if not reasons:
        reasons.append("Basic information is available, but no strong match reason was found yet.")

    return Score(max(0, min(100, score)), tuple(reasons), None)


def can_submit_application(has_approval: bool, submitted_today: int, daily_limit: int) -> tuple[bool, str]:
    if not has_approval:
        return False, "This application has no recorded approval."
    if submitted_today >= daily_limit:
        return False, "The daily limit for this site and account has been reached."
    return True, "Ready for permitted submission."

