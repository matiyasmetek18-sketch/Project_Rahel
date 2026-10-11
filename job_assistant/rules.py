from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
import re

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

CAREGIVER_TERMS = {
    "caregiver",
    "caregiving",
    "care partner",
    "care professional",
    "care aide",
    "home care",
    "home health",
    "personal care",
    "personal care aide",
    "companion",
    "companionship",
    "direct care",
    "resident assistant",
    "medication aide",
    "hca",
    "cna",
    "nac",
    "hha",
    "patient care",
}

NON_CAREGIVER_TERMS = {
    "engineer",
    "software",
    "sales",
    "marketing",
    "designer",
    "product manager",
    "analyst",
    "account executive",
    "recruiter",
    "director",
    "manager",
    "services manager",
    "counsel",
    "credentialing specialist",
    "therapist",
    "associate",
    "reimbursement",
    "collections",
}

DIRECT_CARE_TITLE_TERMS = {
    "caregiver",
    "care navigator",
    "care aide",
    "care professional",
    "home care aide",
    "personal care",
    "companion",
    "direct care",
    "resident assistant",
    "patient care",
    "hca",
    "cna",
    "nac",
}

REQUIRED_CREDENTIAL_PATTERNS = {
    "RN": (r"\brn\b", r"\bregistered nurse\b"),
    "LPN": (r"\blpn\b", r"\blicensed practical nurse\b"),
    "CNA": (r"\bcna\b", r"\bcertified nursing assistant\b"),
    "HCA": (r"\bhca\b", r"\bhome care aide\b"),
    "NAC": (r"\bnac\b", r"\bnursing assistant certified\b"),
    "Nurse Practitioner": (r"\bnurse practitioner\b", r"\bnp\b"),
    "Physician Assistant": (r"\bphysician assistant\b", r"\bpa-c\b"),
    "Physician": (r"\bphysician\b", r"\bdoctor\b", r"\bmd\b", r"\bdo\b"),
}


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


def normalize_terms(value: str) -> tuple[str, ...]:
    return tuple(term.strip().lower() for term in value.split(",") if term.strip())


def posting_text(job: JobPosting) -> str:
    return f"{job.title} {job.company} {job.city} {job.state} {job.employment_type} {job.description}".lower()


def matched_terms(text: str, terms: tuple[str, ...] | set[str]) -> list[str]:
    found: list[str] = []
    for term in terms:
        term = term.lower().strip()
        if not term:
            continue
        if " " in term:
            if term in text:
                found.append(term)
        elif re.search(rf"\b{re.escape(term)}\b", text):
            found.append(term)
    return found


def inferred_required_credentials(job: JobPosting) -> tuple[str, ...]:
    text = posting_text(job)
    inferred = list(job.required_credentials)
    for credential, patterns in REQUIRED_CREDENTIAL_PATTERNS.items():
        if any(re.search(pattern, text) for pattern in patterns) and credential.lower() not in {item.lower() for item in inferred}:
            inferred.append(credential)
    return tuple(inferred)


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


def score_job(
    profile: Profile,
    credentials: list[Credential],
    job: JobPosting,
    as_of: date | None = None,
    preferred_titles: tuple[str, ...] = (),
    search_keywords: tuple[str, ...] = (),
    acceptable_locations: tuple[str, ...] = (),
    employment_types: tuple[str, ...] = (),
    remote_ok: bool = False,
) -> Score:
    score = 35
    reasons: list[str] = []
    missing: list[str] = []
    credential_names = {c.name.lower() for c in credentials if c.is_current(as_of)}
    text = posting_text(job)
    title_text = job.title.lower()

    caregiver_matches = matched_terms(text, CAREGIVER_TERMS)
    title_caregiver_matches = matched_terms(title_text, DIRECT_CARE_TITLE_TERMS)
    preferred_matches = matched_terms(text, preferred_titles)
    keyword_matches = matched_terms(text, search_keywords)
    non_caregiver_matches = matched_terms(title_text, NON_CAREGIVER_TERMS)
    if non_caregiver_matches and not title_caregiver_matches:
        return Score(0, ("Posting title appears unrelated to direct caregiver work.",), "not_caregiver_role")
    if caregiver_matches:
        score += 20
        reasons.append(f"Caregiver relevance: {', '.join(caregiver_matches[:4])}.")
    elif preferred_matches or keyword_matches:
        score += 8
        reasons.append("Posting matches configured search terms, but caregiver relevance is not explicit.")
    elif non_caregiver_matches:
        return Score(0, ("Posting appears unrelated to caregiver work.",), "not_caregiver_role")
    else:
        score -= 25
        reasons.append("Caregiver relevance is unknown from the posting title and description.")

    desired_locations = tuple(profile.acceptable_cities) + tuple(acceptable_locations)
    state_matches = bool(job.state and profile.state and job.state.lower() == profile.state.lower())
    city_matches = bool(job.city and job.city.lower() in {c.lower() for c in desired_locations})

    if city_matches and (not profile.state or not job.state or state_matches):
        score += 20
        reasons.append("City matches the user's acceptable cities.")
    elif state_matches:
        score += 12
        reasons.append("State matches the user's preferred state.")
    elif job.remote and ("remote" in profile.availability.lower() or remote_ok):
        score += 12
        reasons.append("Remote work matches the user's availability.")
    elif job.remote:
        reasons.append("Job appears remote; confirm it fits the user's caregiving preferences.")
    elif desired_locations:
        score -= 15
        reasons.append("City is outside the user's preferred cities.")
    else:
        missing.append("acceptable cities")

    if job.hourly_pay is not None and profile.minimum_hourly_pay is not None:
        if job.hourly_pay >= profile.minimum_hourly_pay:
            score += 15
            reasons.append("Pay meets the user's minimum.")
        else:
            return Score(0, ("Pay is below the user's minimum.",), "pay_below_minimum")
    elif profile.minimum_hourly_pay is None:
        missing.append("minimum pay")
    else:
        reasons.append("Pay was not listed; confirm compensation before applying.")

    missing_credentials = [required for required in inferred_required_credentials(job) if required.lower() not in credential_names]
    if missing_credentials:
        return Score(0, (f"Missing current verified credential: {', '.join(missing_credentials)}.",), "missing_credential")

    if employment_types and job.employment_type:
        if any(term.lower() in job.employment_type.lower() for term in employment_types):
            score += 5
            reasons.append("Employment type matches configured preferences.")
        else:
            score -= 5
            reasons.append("Employment type may not match configured preferences.")
    elif employment_types:
        reasons.append("Employment type was not listed; confirm schedule before applying.")

    if preferred_matches:
        score += min(10, len(preferred_matches) * 3)
        reasons.append(f"Preferred title match: {', '.join(preferred_matches[:4])}.")

    if keyword_matches:
        score += min(10, len(keyword_matches) * 2)
        reasons.append(f"Search keyword match: {', '.join(keyword_matches[:5])}.")

    words = Counter(job.description.lower().replace(",", " ").split())
    matched_skills = [skill for skill in profile.skills if skill.lower() in words]
    if matched_skills:
        score += min(25, len(matched_skills) * 5)
        reasons.append(f"Skills match: {', '.join(matched_skills)}.")
    elif profile.skills:
        reasons.append("No confirmed skills were found in the posting text.")
    else:
        missing.append("confirmed skills")

    if profile.availability and profile.availability.lower() in job.description.lower():
        score += 5
        reasons.append("Posting text appears to match the user's availability.")

    if profile.job_types:
        matched_types = [job_type for job_type in profile.job_types if job_type.lower() in f"{job.title} {job.description}".lower()]
        if matched_types:
            score += 10
            reasons.append(f"Caregiver job type match: {', '.join(matched_types)}.")
        else:
            reasons.append("Posting does not clearly match the preferred caregiver job types.")
    else:
        missing.append("preferred job types")

    if not reasons:
        reasons.append("Basic information is available, but no strong match reason was found yet.")
    if missing:
        reasons.append(f"Missing profile information for scoring: {', '.join(sorted(set(missing)))}.")

    return Score(max(0, min(100, score)), tuple(reasons), None)


def can_submit_application(has_approval: bool, submitted_today: int, daily_limit: int) -> tuple[bool, str]:
    if not has_approval:
        return False, "This application has no recorded approval."
    if submitted_today >= daily_limit:
        return False, "The daily limit for this site and account has been reached."
    return True, "Ready for permitted submission."

