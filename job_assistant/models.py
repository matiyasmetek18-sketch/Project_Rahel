from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Credential:
    name: str
    issuing_body: str
    expiration_date: str | None = None
    verified: bool = False

    def is_current(self, as_of: date | None = None) -> bool:
        if not self.verified:
            return False
        if not self.expiration_date:
            return True
        check_date = as_of or date.today()
        return date.fromisoformat(self.expiration_date) >= check_date


@dataclass(frozen=True)
class Profile:
    full_name: str
    email: str
    phone: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    skills: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    availability: str = ""
    transportation: str = ""
    minimum_hourly_pay: float | None = None
    job_types: tuple[str, ...] = ()
    acceptable_cities: tuple[str, ...] = ()
    confirmed_resume_summary: str = ""

    def answers(self) -> dict[str, str]:
        values = {
            "name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "city": self.city,
            "state": self.state,
            "zip": self.zip_code,
            "resume": self.confirmed_resume_summary,
        }
        return {key: value for key, value in values.items() if value}


@dataclass(frozen=True)
class JobPosting:
    source_site: str
    external_id: str
    title: str
    company: str
    city: str
    state: str
    url: str
    description: str = ""
    required_fields: tuple[str, ...] = ()
    required_credentials: tuple[str, ...] = ()
    hourly_pay: float | None = None

