from __future__ import annotations

from .models import JobPosting, Profile


def make_resume_summary(profile: Profile) -> tuple[str, tuple[str, ...]]:
    if profile.confirmed_resume_summary:
        return profile.confirmed_resume_summary, ()
    return "", ("Confirm a resume summary before drafting applications.",)


def make_cover_letter(profile: Profile, job: JobPosting) -> tuple[str, tuple[str, ...]]:
    missing = []
    if not profile.full_name:
        missing.append("name")
    if not profile.confirmed_resume_summary:
        missing.append("confirmed resume summary")
    if missing:
        return "", tuple(f"Missing required stored value: {item}" for item in missing)

    letter = (
        f"Dear hiring team at {job.company},\n\n"
        f"I am interested in the {job.title} role. {profile.confirmed_resume_summary}\n\n"
        "I would appreciate the opportunity to discuss how my experience fits this role.\n\n"
        f"Sincerely,\n{profile.full_name}"
    )
    return letter, ()

