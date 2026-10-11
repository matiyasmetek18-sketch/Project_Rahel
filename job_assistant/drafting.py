from __future__ import annotations

from .models import JobPosting, Profile


def sentence_join(parts: list[str]) -> str:
    return " ".join(part.strip() for part in parts if part.strip())


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

    details = [
        profile.confirmed_resume_summary,
        f"My confirmed skills include {', '.join(profile.skills)}." if profile.skills else "",
        f"I am available for {profile.availability}." if profile.availability else "",
        f"I am seeking roles in {', '.join(profile.acceptable_cities)}." if profile.acceptable_cities else "",
    ]
    fit = sentence_join(details)
    letter = (
        f"Dear hiring team at {job.company},\n\n"
        f"I am interested in the {job.title} role. {fit}\n\n"
        "I would appreciate the opportunity to discuss how my experience fits this role.\n\n"
        f"Sincerely,\n{profile.full_name}"
    )
    return letter, ()


def make_form_answers(profile: Profile, work_history_rows) -> str:
    answers = []
    if profile.full_name:
        answers.append(f"Name: {profile.full_name}")
    if profile.email:
        answers.append(f"Email: {profile.email}")
    if profile.phone:
        answers.append(f"Phone: {profile.phone}")
    if profile.city or profile.state or profile.zip_code:
        answers.append(f"Location: {profile.city}, {profile.state} {profile.zip_code}".strip())
    if profile.languages:
        answers.append(f"Languages: {', '.join(profile.languages)}")
    if profile.availability:
        answers.append(f"Availability: {profile.availability}")
    if profile.transportation:
        answers.append(f"Transportation: {profile.transportation}")
    if profile.skills:
        answers.append(f"Confirmed skills: {', '.join(profile.skills)}")
    for row in work_history_rows:
        end_date = row["end_date"] or "Present"
        answers.append(f"Experience: {row['title']} at {row['employer']} ({row['start_date']} to {end_date}) - {row['tasks']}")
    return "\n".join(answers)

