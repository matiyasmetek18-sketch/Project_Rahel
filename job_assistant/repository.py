from __future__ import annotations

import json
from pathlib import Path

from .db import get_connection, utc_now
from .drafting import make_cover_letter, make_resume_summary
from .models import Credential, JobPosting, Profile
from .rules import can_submit_application, classify_easy_apply, score_job
from .security import hash_password, verify_password
from .workflow import (
    APPROVED,
    DISCOVERED,
    FAILED,
    OPENED_FOR_MANUAL_SUBMISSION,
    PENDING_REVIEW,
    PREPARED,
    REJECTED,
    SUBMITTED,
    can_transition,
)


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
            conn.execute("INSERT INTO job_search_settings (user_id) VALUES (?)", (user_id,))
            conn.execute("INSERT INTO account_settings (user_id) VALUES (?)", (user_id,))
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
                 required_fields, required_credentials, hourly_pay, employment_type, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    job.hourly_pay,
                    "",
                    DISCOVERED,
                    utc_now(),
                    utc_now(),
                ),
            )
            return int(cur.lastrowid)

    def upsert_job(self, user_id: int, job: JobPosting) -> tuple[int, bool]:
        now = utc_now()
        with get_connection(self.db_path) as conn:
            existing = conn.execute(
                "SELECT id FROM job_postings WHERE user_id = ? AND source_site = ? AND external_id = ?",
                (user_id, job.source_site, job.external_id),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE job_postings
                    SET title = ?, company = ?, city = ?, state = ?, url = ?, description = ?,
                        required_fields = ?, required_credentials = ?, hourly_pay = ?, updated_at = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (
                        job.title,
                        job.company,
                        job.city,
                        job.state,
                        job.url,
                        job.description,
                        ",".join(job.required_fields),
                        ",".join(job.required_credentials),
                        job.hourly_pay,
                        now,
                        existing["id"],
                        user_id,
                    ),
                )
                return int(existing["id"]), False
            cur = conn.execute(
                """
                INSERT INTO job_postings
                (user_id, source_site, external_id, title, company, city, state, url, description,
                 required_fields, required_credentials, hourly_pay, employment_type, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?)
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
                    job.hourly_pay,
                    DISCOVERED,
                    now,
                    now,
                ),
            )
            return int(cur.lastrowid), True

    def list_jobs(self, user_id: int):
        with get_connection(self.db_path) as conn:
            return conn.execute(
                """
                SELECT job_postings.*,
                       application_drafts.id AS draft_id,
                       application_drafts.label,
                       application_drafts.score,
                       application_drafts.reasons,
                       application_drafts.status AS draft_status
                FROM job_postings
                LEFT JOIN application_drafts
                  ON application_drafts.job_id = job_postings.id
                 AND application_drafts.user_id = job_postings.user_id
                WHERE job_postings.user_id = ?
                ORDER BY job_postings.created_at DESC, job_postings.id DESC
                """,
                (user_id,),
            ).fetchall()

    def get_job(self, user_id: int, job_id: int):
        with get_connection(self.db_path) as conn:
            return conn.execute("SELECT * FROM job_postings WHERE id = ? AND user_id = ?", (job_id, user_id)).fetchone()

    def prepare_job(self, user_id: int, job_id: int) -> int:
        profile = self.profile_for_user(user_id)
        credentials = self.credentials_for_user(user_id)
        with get_connection(self.db_path) as conn:
            job_row = conn.execute("SELECT * FROM job_postings WHERE id = ? AND user_id = ?", (job_id, user_id)).fetchone()
            if not job_row:
                raise PermissionError("Job does not belong to this account.")
            job = row_to_job(job_row)
            classification = classify_easy_apply(profile, job)
            scored = score_job(profile, credentials, job)
            resume_summary, resume_questions = make_resume_summary(profile)
            cover_letter, cover_questions = make_cover_letter(profile, job)
            questions = tuple(classification.unanswered_questions) + tuple(resume_questions) + tuple(cover_questions)
            now = utc_now()
            existing = conn.execute(
                "SELECT id FROM application_drafts WHERE user_id = ? AND job_id = ?",
                (user_id, job_id),
            ).fetchone()
            if existing:
                draft_id = int(existing["id"])
                conn.execute(
                    """
                    UPDATE application_drafts
                    SET label = ?, score = ?, reasons = ?, unanswered_questions = ?, resume_summary = ?,
                        cover_letter = ?, form_answers = ?, status = ?, updated_at = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (
                        classification.label,
                        scored.value,
                        json.dumps(list(scored.reasons) + list(classification.reasons)),
                        json.dumps(questions),
                        resume_summary,
                        cover_letter,
                        json.dumps({}),
                        PENDING_REVIEW,
                        now,
                        draft_id,
                        user_id,
                    ),
                )
            else:
                cur = conn.execute(
                    """
                    INSERT INTO application_drafts
                    (user_id, job_id, label, score, reasons, unanswered_questions, resume_summary,
                     cover_letter, form_answers, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        job_id,
                        classification.label,
                        scored.value,
                        json.dumps(list(scored.reasons) + list(classification.reasons)),
                        json.dumps(questions),
                        resume_summary,
                        cover_letter,
                        json.dumps({}),
                        PENDING_REVIEW,
                        now,
                        now,
                    ),
                )
                draft_id = int(cur.lastrowid)
            conn.execute(
                "UPDATE job_postings SET status = ?, exclusion_reason = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (PREPARED, scored.exclusion_reason or "", now, job_id, user_id),
            )
            conn.execute(
                """
                INSERT INTO application_events (user_id, draft_id, source_site, event_type, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, draft_id, job.source_site, PREPARED, "Application draft prepared for review.", now),
            )
            return draft_id

    def list_review_queue(self, user_id: int):
        with get_connection(self.db_path) as conn:
            return conn.execute(
                """
                SELECT application_drafts.*, job_postings.title, job_postings.company, job_postings.url, job_postings.source_site
                FROM application_drafts
                JOIN job_postings ON job_postings.id = application_drafts.job_id
                WHERE application_drafts.user_id = ?
                  AND application_drafts.status IN ('pending_review', 'approved', 'opened_for_manual_submission', 'not_submitted')
                ORDER BY application_drafts.created_at DESC
                """,
                (user_id,),
            ).fetchall()

    def get_draft(self, user_id: int, draft_id: int):
        with get_connection(self.db_path) as conn:
            return conn.execute(
                """
                SELECT application_drafts.*, job_postings.title, job_postings.company, job_postings.url, job_postings.source_site
                FROM application_drafts
                JOIN job_postings ON job_postings.id = application_drafts.job_id
                WHERE application_drafts.id = ? AND application_drafts.user_id = ?
                """,
                (draft_id, user_id),
            ).fetchone()

    def update_draft_text(self, user_id: int, draft_id: int, resume_summary: str, cover_letter: str, form_answers: str) -> None:
        with get_connection(self.db_path) as conn:
            owner = conn.execute("SELECT id FROM application_drafts WHERE id = ? AND user_id = ?", (draft_id, user_id)).fetchone()
            if not owner:
                raise PermissionError("Draft does not belong to this account.")
            conn.execute(
                """
                UPDATE application_drafts
                SET resume_summary = ?, cover_letter = ?, form_answers = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (resume_summary, cover_letter, form_answers, utc_now(), draft_id, user_id),
            )

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
                "SELECT id, status FROM application_drafts WHERE id = ? AND user_id = ?",
                (draft_id, user_id),
            ).fetchone()
            if not owner:
                raise PermissionError("Draft does not belong to this account.")
            transition = can_transition(owner["status"], APPROVED)
            if not transition.ok:
                raise ValueError(transition.message)
            cur = conn.execute(
                """
                INSERT INTO approvals (user_id, draft_id, approved_at, approved_count, confirmation_text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, draft_id, utc_now(), approved_count, confirmation_text),
            )
            conn.execute(
                "UPDATE application_drafts SET status = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (APPROVED, utc_now(), draft_id, user_id),
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

    def reject_draft(self, user_id: int, draft_id: int, reason: str = "") -> None:
        self.transition_draft(user_id, draft_id, REJECTED, reason or "Rejected by user.")

    def open_for_manual_submission(self, user_id: int, draft_id: int) -> str:
        settings = self.account_settings(user_id)
        if settings["pause_all"]:
            raise ValueError("Pause-all is enabled. Turn it off before opening applications.")
        draft = self.get_draft(user_id, draft_id)
        if not draft:
            raise PermissionError("Draft does not belong to this account.")
        daily_limit = self.daily_limit_for_site(user_id, draft["source_site"])
        ok, message = can_submit_application(
            self.has_approval(user_id, draft_id),
            self.count_submissions_today(user_id, draft["source_site"]),
            daily_limit,
        )
        if not ok:
            raise ValueError(message)
        self.transition_draft(user_id, draft_id, OPENED_FOR_MANUAL_SUBMISSION, "User opened the application URL for manual submission.")
        return draft["url"]

    def confirm_manual_submission(self, user_id: int, draft_id: int, submitted: bool, note: str = "") -> None:
        new_state = SUBMITTED if submitted else "not_submitted"
        self.transition_draft(user_id, draft_id, new_state, note or ("User confirmed submission." if submitted else "User marked as not submitted."))

    def transition_draft(self, user_id: int, draft_id: int, new_status: str, message: str) -> None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT application_drafts.status, job_postings.source_site
                FROM application_drafts
                JOIN job_postings ON job_postings.id = application_drafts.job_id
                WHERE application_drafts.id = ? AND application_drafts.user_id = ?
                """,
                (draft_id, user_id),
            ).fetchone()
            if not row:
                raise PermissionError("Draft does not belong to this account.")
            transition = can_transition(row["status"], new_status)
            if not transition.ok:
                raise ValueError(transition.message)
            now = utc_now()
            conn.execute(
                "UPDATE application_drafts SET status = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (new_status, now, draft_id, user_id),
            )
            event_type = "submitted" if new_status == SUBMITTED else new_status
            conn.execute(
                """
                INSERT INTO application_events (user_id, draft_id, source_site, event_type, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, draft_id, row["source_site"], event_type, message, now),
            )

    def application_history(self, user_id: int):
        with get_connection(self.db_path) as conn:
            return conn.execute(
                """
                SELECT application_drafts.status, application_drafts.updated_at, job_postings.title,
                       job_postings.company, job_postings.source_site, job_postings.url
                FROM application_drafts
                JOIN job_postings ON job_postings.id = application_drafts.job_id
                WHERE application_drafts.user_id = ?
                ORDER BY application_drafts.updated_at DESC, application_drafts.created_at DESC
                """,
                (user_id,),
            ).fetchall()

    def dashboard_counts(self, user_id: int) -> dict[str, int]:
        with get_connection(self.db_path) as conn:
            jobs = conn.execute("SELECT COUNT(*) AS count FROM job_postings WHERE user_id = ?", (user_id,)).fetchone()["count"]
            pending = conn.execute(
                "SELECT COUNT(*) AS count FROM application_drafts WHERE user_id = ? AND status = ?",
                (user_id, PENDING_REVIEW),
            ).fetchone()["count"]
            approved = conn.execute(
                "SELECT COUNT(*) AS count FROM application_drafts WHERE user_id = ? AND status = ?",
                (user_id, APPROVED),
            ).fetchone()["count"]
            history = conn.execute("SELECT COUNT(*) AS count FROM application_drafts WHERE user_id = ?", (user_id,)).fetchone()["count"]
        return {"jobs": int(jobs), "pending": int(pending), "approved": int(approved), "history": int(history)}

    def credentials_rows(self, user_id: int):
        with get_connection(self.db_path) as conn:
            return conn.execute("SELECT * FROM credentials WHERE user_id = ? ORDER BY name", (user_id,)).fetchall()

    def update_credential(self, user_id: int, credential_id: int, credential: Credential) -> None:
        with get_connection(self.db_path) as conn:
            result = conn.execute(
                """
                UPDATE credentials
                SET name = ?, issuing_body = ?, expiration_date = ?, verified = ?
                WHERE id = ? AND user_id = ?
                """,
                (credential.name, credential.issuing_body, credential.expiration_date, int(credential.verified), credential_id, user_id),
            )
            if result.rowcount != 1:
                raise PermissionError("Credential does not belong to this account.")

    def work_history_rows(self, user_id: int):
        with get_connection(self.db_path) as conn:
            return conn.execute("SELECT * FROM work_history WHERE user_id = ? ORDER BY start_date DESC", (user_id,)).fetchall()

    def add_work_history(self, user_id: int, employer: str, title: str, start_date: str, end_date: str, tasks: str) -> int:
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO work_history (user_id, employer, title, start_date, end_date, tasks)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, employer, title, start_date, end_date, tasks),
            )
            return int(cur.lastrowid)

    def search_settings(self, user_id: int):
        with get_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM job_search_settings WHERE user_id = ?", (user_id,)).fetchone()
            if not row:
                conn.execute("INSERT INTO job_search_settings (user_id) VALUES (?)", (user_id,))
                row = conn.execute("SELECT * FROM job_search_settings WHERE user_id = ?", (user_id,)).fetchone()
            return row

    def update_search_settings(self, user_id: int, **values) -> None:
        allowed = {"job_titles", "acceptable_locations", "minimum_pay", "employment_types", "search_keywords", "remote_ok"}
        fields = [key for key in values if key in allowed]
        if not fields:
            return
        with get_connection(self.db_path) as conn:
            conn.execute("INSERT OR IGNORE INTO job_search_settings (user_id) VALUES (?)", (user_id,))
            conn.execute(
                f"UPDATE job_search_settings SET {', '.join(field + ' = ?' for field in fields)} WHERE user_id = ?",
                [values[field] for field in fields] + [user_id],
            )

    def account_settings(self, user_id: int):
        with get_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM account_settings WHERE user_id = ?", (user_id,)).fetchone()
            if not row:
                conn.execute("INSERT INTO account_settings (user_id) VALUES (?)", (user_id,))
                row = conn.execute("SELECT * FROM account_settings WHERE user_id = ?", (user_id,)).fetchone()
            return row

    def update_account_settings(self, user_id: int, default_daily_limit: int, pause_all: bool, high_contrast: bool, large_text: bool) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute("INSERT OR IGNORE INTO account_settings (user_id) VALUES (?)", (user_id,))
            conn.execute(
                """
                UPDATE account_settings
                SET default_daily_limit = ?, pause_all = ?, high_contrast = ?, large_text = ?
                WHERE user_id = ?
                """,
                (default_daily_limit, int(pause_all), int(high_contrast), int(large_text), user_id),
            )

    def daily_limit_for_site(self, user_id: int, source_site: str) -> int:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT daily_limit FROM site_limits WHERE user_id = ? AND source_site = ?",
                (user_id, source_site),
            ).fetchone()
            if row:
                return int(row["daily_limit"])
            settings = conn.execute("SELECT default_daily_limit FROM account_settings WHERE user_id = ?", (user_id,)).fetchone()
            return int(settings["default_daily_limit"]) if settings else 5

    def latest_resume(self, user_id: int):
        with get_connection(self.db_path) as conn:
            return conn.execute(
                "SELECT * FROM resumes WHERE user_id = ? ORDER BY uploaded_at DESC, id DESC LIMIT 1",
                (user_id,),
            ).fetchone()


def split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def row_to_job(row) -> JobPosting:
    return JobPosting(
        source_site=row["source_site"],
        external_id=row["external_id"],
        title=row["title"],
        company=row["company"],
        city=row["city"],
        state=row["state"],
        url=row["url"],
        description=row["description"],
        required_fields=split_csv(row["required_fields"]),
        required_credentials=split_csv(row["required_credentials"]),
        hourly_pay=row["hourly_pay"],
    )
