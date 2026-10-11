from __future__ import annotations

import json
from pathlib import Path

from .db import get_connection, utc_now
from .discovery import adapter_for
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
                 required_fields, required_credentials, hourly_pay, employment_type, remote,
                 source_metadata, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    job.employment_type,
                    int(job.remote),
                    job.source_metadata,
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
                        required_fields = ?, required_credentials = ?, hourly_pay = ?, employment_type = ?,
                        remote = ?, source_metadata = ?, updated_at = ?
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
                        job.employment_type,
                        int(job.remote),
                        job.source_metadata,
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
                 required_fields, required_credentials, hourly_pay, employment_type, remote,
                 source_metadata, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    job.employment_type,
                    int(job.remote),
                    job.source_metadata,
                    DISCOVERED,
                    now,
                    now,
                ),
            )
            return int(cur.lastrowid), True

    def list_jobs(self, user_id: int):
        profile = self.profile_for_user(user_id)
        credentials = self.credentials_for_user(user_id)
        settings = self.search_settings(user_id)
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
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
        ranked = []
        for row in rows:
            if row["draft_id"] is not None:
                score = row["score"]
                reasons = row["reasons"]
                exclusion_reason = row["exclusion_reason"]
            else:
                scored = score_job_with_settings(profile, credentials, row_to_job(row), settings)
                score = scored.value
                reasons = json.dumps(scored.reasons)
                exclusion_reason = scored.exclusion_reason or row["exclusion_reason"]
            ranked.append({"row": row, "feed_score": score, "feed_reasons": reasons, "feed_exclusion": exclusion_reason})
        ranked.sort(key=lambda item: (-int(item["feed_score"]), item["row"]["created_at"], item["row"]["id"]))
        return ranked

    def job_feed_metrics(self, user_id: int) -> dict[str, int]:
        jobs = self.list_jobs(user_id)
        return {
            "valid_listings": len(jobs),
            "relevant_listings": sum(1 for job in jobs if job["feed_exclusion"] != "not_caregiver_role" and int(job["feed_score"]) > 0),
            "likely_eligible": sum(1 for job in jobs if not job["feed_exclusion"] and int(job["feed_score"]) >= 60),
            "stale_listings": sum(1 for job in jobs if job["row"]["status"] == "stale"),
            "unknown_qualification": sum(1 for job in jobs if "Missing profile information" in job["feed_reasons"] or "confirm" in job["feed_reasons"].lower()),
        }

    def get_job(self, user_id: int, job_id: int):
        with get_connection(self.db_path) as conn:
            return conn.execute("SELECT * FROM job_postings WHERE id = ? AND user_id = ?", (job_id, user_id)).fetchone()

    def prepare_job(self, user_id: int, job_id: int) -> int:
        profile = self.profile_for_user(user_id)
        credentials = self.credentials_for_user(user_id)
        settings = self.search_settings(user_id)
        with get_connection(self.db_path) as conn:
            job_row = conn.execute("SELECT * FROM job_postings WHERE id = ? AND user_id = ?", (job_id, user_id)).fetchone()
            if not job_row:
                raise PermissionError("Job does not belong to this account.")
            job = row_to_job(job_row)
            classification = classify_easy_apply(profile, job)
            scored = score_job_with_settings(profile, credentials, job, settings)
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

    def record_resume(
        self,
        user_id: int,
        original_filename: str,
        stored_path: str,
        content_type: str,
        extracted_text: str = "",
        extracted_json: str = "",
    ) -> int:
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO resumes
                (user_id, original_filename, stored_path, content_type, uploaded_at, extracted_text, extracted_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, original_filename, stored_path, content_type, utc_now(), extracted_text, extracted_json),
            )
            return int(cur.lastrowid)

    def confirm_resume_extraction(self, user_id: int, resume_id: int, summary: str, skills: str) -> None:
        with get_connection(self.db_path) as conn:
            row = conn.execute("SELECT id FROM resumes WHERE id = ? AND user_id = ?", (resume_id, user_id)).fetchone()
            if not row:
                raise PermissionError("Resume does not belong to this account.")
            conn.execute("UPDATE resumes SET confirmed = 1 WHERE id = ? AND user_id = ?", (resume_id, user_id))
            conn.execute(
                """
                UPDATE profiles
                SET confirmed_resume_summary = ?, skills = ?
                WHERE user_id = ?
                """,
                (summary, skills, user_id),
            )

    def approve_draft(self, user_id: int, draft_id: int, confirmation_text: str, approved_count: int = 1) -> int:
        with get_connection(self.db_path) as conn:
            owner = conn.execute(
                "SELECT id, status, unanswered_questions, form_answers FROM application_drafts WHERE id = ? AND user_id = ?",
                (draft_id, user_id),
            ).fetchone()
            if not owner:
                raise PermissionError("Draft does not belong to this account.")
            transition = can_transition(owner["status"], APPROVED)
            if not transition.ok:
                raise ValueError(transition.message)
            if has_unanswered_questions(owner["unanswered_questions"]) and not has_meaningful_form_answers(owner["form_answers"]):
                raise ValueError("Answer the listed required questions before approving this application.")
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

    def add_job_source(self, user_id: int, provider: str, board_identifier: str, display_name: str = "") -> int:
        now = utc_now()
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                """
                INSERT INTO job_sources (user_id, provider, board_identifier, display_name, active, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
                ON CONFLICT(user_id, provider, board_identifier)
                DO UPDATE SET display_name = excluded.display_name, active = 1
                """,
                (user_id, provider, board_identifier.strip(), display_name.strip(), now),
            )
            if cur.lastrowid:
                return int(cur.lastrowid)
            row = conn.execute(
                "SELECT id FROM job_sources WHERE user_id = ? AND provider = ? AND board_identifier = ?",
                (user_id, provider, board_identifier.strip()),
            ).fetchone()
            return int(row["id"])

    def list_job_sources(self, user_id: int):
        with get_connection(self.db_path) as conn:
            return conn.execute(
                "SELECT * FROM job_sources WHERE user_id = ? ORDER BY provider, display_name, board_identifier",
                (user_id,),
            ).fetchall()

    def fetch_jobs_from_sources(self, user_id: int) -> dict[str, int | list[str]]:
        created = 0
        updated = 0
        found = 0
        duplicates = 0
        stale_total = 0
        errors: list[str] = []
        sources = self.list_job_sources(user_id)
        for source in sources:
            if not source["active"]:
                continue
            try:
                result = adapter_for(source["provider"]).fetch_jobs(source["board_identifier"])
                found += len(result.jobs)
                seen_external_ids: set[str] = set()
                for job in result.jobs:
                    seen_external_ids.add(job.external_id)
                    _, was_created = self.upsert_job(user_id, job)
                    created += int(was_created)
                    if was_created:
                        continue
                    updated += 1
                    duplicates += 1
                stale = self.mark_stale_jobs_for_source(user_id, f"{source['provider']}:{source['board_identifier']}", seen_external_ids)
                self.update_job_source_status(user_id, source["id"], result.source_status)
                stale_total += stale
                updated += stale
            except Exception as exc:
                message = str(exc)
                errors.append(f"{source['provider']} {source['board_identifier']}: {message}")
                self.update_job_source_status(user_id, source["id"], message)
        return {"found": found, "created": created, "updated": updated, "duplicates": duplicates, "stale": stale_total, "errors": errors}

    def mark_stale_jobs_for_source(self, user_id: int, source_site: str, current_external_ids: set[str]) -> int:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT id, external_id FROM job_postings
                WHERE user_id = ? AND source_site = ? AND status != 'stale'
                """,
                (user_id, source_site),
            ).fetchall()
            stale_ids = [row["id"] for row in rows if row["external_id"] not in current_external_ids]
            for job_id in stale_ids:
                conn.execute(
                    "UPDATE job_postings SET status = 'stale', exclusion_reason = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                    ("No longer returned by the configured job board.", utc_now(), job_id, user_id),
                )
            return len(stale_ids)

    def update_job_source_status(self, user_id: int, source_id: int, status: str) -> None:
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                UPDATE job_sources
                SET last_status = ?, last_fetched_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (status, utc_now(), source_id, user_id),
            )


def split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def score_job_with_settings(profile: Profile, credentials: list[Credential], job: JobPosting, settings) -> object:
    return score_job(
        profile,
        credentials,
        job,
        preferred_titles=split_csv(settings["job_titles"] if settings else ""),
        search_keywords=split_csv(settings["search_keywords"] if settings else ""),
        acceptable_locations=split_csv(settings["acceptable_locations"] if settings else ""),
        employment_types=split_csv(settings["employment_types"] if settings else ""),
        remote_ok=bool(settings["remote_ok"]) if settings else False,
    )


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
        employment_type=row["employment_type"],
        remote=bool(row["remote"]),
        source_metadata=row["source_metadata"],
    )


def has_unanswered_questions(value: str) -> bool:
    if not value:
        return False
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return bool(value.strip())
    if isinstance(parsed, list):
        return any(str(item).strip() for item in parsed)
    return bool(parsed)


def has_meaningful_form_answers(value: str) -> bool:
    if not value or not value.strip():
        return False
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return bool(value.strip())
    if isinstance(parsed, dict):
        return any(str(key).strip() and str(val).strip() for key, val in parsed.items())
    if isinstance(parsed, list):
        return any(str(item).strip() for item in parsed)
    return bool(str(parsed).strip())
