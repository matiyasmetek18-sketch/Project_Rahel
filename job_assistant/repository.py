from __future__ import annotations

from pathlib import Path

from .db import get_connection, utc_now
from .models import Credential, JobPosting, Profile
from .security import hash_password, verify_password


class Repository:
    def __init__(self, db_path: Path | str):
        self.db_path = db_path

    def create_user(self, username: str, email: str, password: str) -> int:
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (username, email, hash_password(password), utc_now()),
            )
            user_id = int(cur.lastrowid)
            conn.execute("INSERT INTO profiles (user_id) VALUES (?)", (user_id,))
            return user_id

    def authenticate(self, username: str, password: str):
        with get_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if row and verify_password(password, row["password_hash"]):
                return row
            return None

    def get_user(self, user_id: int):
        with get_connection(self.db_path) as conn:
            return conn.execute("SELECT id, username, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()

    def update_profile(self, user_id: int, **values) -> None:
        allowed = {
            "full_name",
            "phone",
            "city",
            "state",
            "zip_code",
            "skills",
            "languages",
            "availability",
            "transportation",
            "minimum_hourly_pay",
            "job_types",
            "acceptable_cities",
            "confirmed_resume_summary",
        }
        fields = [key for key in values if key in allowed]
        if not fields:
            return
        assignments = ", ".join(f"{field} = ?" for field in fields)
        params = [values[field] for field in fields]
        params.append(user_id)
        with get_connection(self.db_path) as conn:
            conn.execute(f"UPDATE profiles SET {assignments} WHERE user_id = ?", params)

    def profile_for_user(self, user_id: int) -> Profile:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT users.email, profiles.* FROM profiles
                JOIN users ON users.id = profiles.user_id
                WHERE profiles.user_id = ?
                """,
                (user_id,),
            ).fetchone()
        if not row:
            raise LookupError("Profile not found.")
        return Profile(
            full_name=row["full_name"],
            email=row["email"],
            phone=row["phone"],
            city=row["city"],
            state=row["state"],
            zip_code=row["zip_code"],
            skills=split_csv(row["skills"]),
            languages=split_csv(row["languages"]),
            availability=row["availability"],
            transportation=row["transportation"],
            minimum_hourly_pay=row["minimum_hourly_pay"],
            job_types=split_csv(row["job_types"]),
            acceptable_cities=split_csv(row["acceptable_cities"]),
            confirmed_resume_summary=row["confirmed_resume_summary"],
        )

    def add_credential(self, user_id: int, credential: Credential) -> int:
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO credentials (user_id, name, issuing_body, expiration_date, verified)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, credential.name, credential.issuing_body, credential.expiration_date, int(credential.verified)),
            )
            return int(cur.lastrowid)

    def credentials_for_user(self, user_id: int) -> list[Credential]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM credentials WHERE user_id = ?", (user_id,)).fetchall()
        return [
            Credential(row["name"], row["issuing_body"], row["expiration_date"], bool(row["verified"]))
            for row in rows
        ]

    def add_job(self, user_id: int, job: JobPosting) -> int:
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO job_postings
                (user_id, source_site, external_id, title, company, city, state, url, description,
                 required_fields, required_credentials, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    job.source_site,
                    job.external_id,
                    job.title,
                    job.company,
                    job.city,
                    job.state,
                    job.url,
                    job.description,
                    ",".join(job.required_fields),
                    ",".join(job.required_credentials),
                    utc_now(),
                ),
            )
            return int(cur.lastrowid)

    def record_resume(self, user_id: int, original_filename: str, stored_path: str, content_type: str) -> int:
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO resumes (user_id, original_filename, stored_path, content_type, uploaded_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, original_filename, stored_path, content_type, utc_now()),
            )
            return int(cur.lastrowid)

    def approve_draft(self, user_id: int, draft_id: int, confirmation_text: str, approved_count: int = 1) -> int:
        with get_connection(self.db_path) as conn:
            owner = conn.execute(
                "SELECT id FROM application_drafts WHERE id = ? AND user_id = ?",
                (draft_id, user_id),
            ).fetchone()
            if not owner:
                raise PermissionError("Draft does not belong to this account.")
            cur = conn.execute(
                """
                INSERT INTO approvals (user_id, draft_id, approved_at, approved_count, confirmation_text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, draft_id, utc_now(), approved_count, confirmation_text),
            )
            return int(cur.lastrowid)

    def has_approval(self, user_id: int, draft_id: int) -> bool:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT id FROM approvals WHERE user_id = ? AND draft_id = ?",
                (user_id, draft_id),
            ).fetchone()
            return row is not None

    def count_submissions_today(self, user_id: int, source_site: str) -> int:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count FROM application_events
                WHERE user_id = ? AND source_site = ? AND event_type = 'submitted'
                AND substr(created_at, 1, 10) = substr(datetime('now'), 1, 10)
                """,
                (user_id, source_site),
            ).fetchone()
            return int(row["count"])


def split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())

