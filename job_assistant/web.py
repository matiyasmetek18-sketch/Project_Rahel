from __future__ import annotations

import json
import os
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, session, url_for

from .config import Config
from .db import init_db
from .importer import parse_job_json
from .models import Credential
from .repository import Repository
from .resume_intelligence import extract_resume
from .resumes import ALLOWED_EXTENSIONS, stored_resume_path, validate_resume_file
from .security import issue_csrf_token, login_required, validate_csrf


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["RESUME_DIR"]).mkdir(parents=True, exist_ok=True)
    init_db(app.config["DATABASE"])

    @app.template_filter("json_items")
    def json_items(value: str):
        if not value:
            return []
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [value]
        if isinstance(parsed, dict):
            return [f"{key}: {val}" for key, val in parsed.items()]
        if isinstance(parsed, list):
            return parsed
        return [str(parsed)]

    @app.before_request
    def load_user():
        g.repo = Repository(app.config["DATABASE"])
        user_id = session.get("user_id")
        g.user = g.repo.get_user(user_id) if user_id else None
        g.settings = g.repo.account_settings(user_id) if g.user else None

    @app.context_processor
    def inject_globals():
        return {"csrf_token": issue_csrf_token}

    @app.get("/")
    def index():
        return redirect(url_for("dashboard" if g.user else "signin"))

    @app.route("/signin", methods=["GET", "POST"])
    def signin():
        if request.method == "POST":
            validate_csrf()
            user = g.repo.authenticate(request.form["username"], request.form["password"])
            if user:
                session.clear()
                session["user_id"] = user["id"]
                issue_csrf_token()
                return redirect(url_for("dashboard"))
            flash("Sign-in failed. Check the username and password.", "error")
        return render_template("signin.html")

    @app.post("/signout")
    @login_required
    def signout():
        validate_csrf()
        session.clear()
        return redirect(url_for("signin"))

    @app.get("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html", counts=g.repo.dashboard_counts(g.user["id"]))

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        if request.method == "POST":
            validate_csrf()
            g.repo.update_profile(
                g.user["id"],
                full_name=request.form.get("full_name", ""),
                phone=request.form.get("phone", ""),
                city=request.form.get("city", ""),
                state=request.form.get("state", ""),
                zip_code=request.form.get("zip_code", ""),
                skills=request.form.get("skills", ""),
                languages=request.form.get("languages", ""),
                availability=request.form.get("availability", ""),
                transportation=request.form.get("transportation", ""),
                minimum_hourly_pay=parse_float(request.form.get("minimum_hourly_pay")),
                job_types=request.form.get("job_types", ""),
                acceptable_cities=request.form.get("acceptable_cities", ""),
                confirmed_resume_summary=request.form.get("confirmed_resume_summary", ""),
            )
            if request.form.get("employer") and request.form.get("title") and request.form.get("start_date"):
                g.repo.add_work_history(
                    g.user["id"],
                    request.form["employer"],
                    request.form["title"],
                    request.form["start_date"],
                    request.form.get("end_date", ""),
                    request.form.get("tasks", ""),
                )
            flash("Profile saved.", "success")
            return redirect(url_for("profile"))
        return render_template(
            "profile.html",
            profile=g.repo.profile_for_user(g.user["id"]),
            history=g.repo.work_history_rows(g.user["id"]),
        )

    @app.route("/credentials", methods=["GET", "POST"])
    @login_required
    def credentials():
        if request.method == "POST":
            validate_csrf()
            credential = Credential(
                name=request.form.get("name", "").strip(),
                issuing_body=request.form.get("issuing_body", "").strip(),
                expiration_date=request.form.get("expiration_date") or None,
                verified=bool(request.form.get("verified")),
            )
            if not credential.name or not credential.issuing_body:
                flash("Credential name and issuing body are required.", "error")
            elif request.form.get("credential_id"):
                g.repo.update_credential(g.user["id"], int(request.form["credential_id"]), credential)
                flash("Credential updated.", "success")
            else:
                g.repo.add_credential(g.user["id"], credential)
                flash("Credential added.", "success")
            return redirect(url_for("credentials"))
        return render_template("credentials.html", credentials=g.repo.credentials_rows(g.user["id"]))

    @app.route("/resume", methods=["GET", "POST"])
    @login_required
    def resume_upload():
        if request.method == "POST":
            validate_csrf()
            uploaded = request.files.get("resume")
            if not uploaded or uploaded.filename == "":
                flash("Choose a PDF or DOCX resume.", "error")
            else:
                uploaded.seek(0, os.SEEK_END)
                size = uploaded.tell()
                uploaded.seek(0)
                ok, message = validate_resume_file(uploaded.filename, size, uploaded.stream)
                if ok:
                    destination = stored_resume_path(Path(app.config["RESUME_DIR"]), g.user["id"], uploaded.filename)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    uploaded.save(destination)
                    content_type = ALLOWED_EXTENSIONS[destination.suffix.lower()]
                    extraction = extract_resume(destination)
                    g.repo.record_resume(
                        g.user["id"],
                        uploaded.filename,
                        str(destination),
                        content_type,
                        extraction.text,
                        json.dumps(extraction.to_dict()),
                    )
                    flash("Resume uploaded. Confirm the summary before using it in drafts.", "success")
                else:
                    flash(message, "error")
            return redirect(url_for("resume_upload"))
        resume = g.repo.latest_resume(g.user["id"])
        extracted = {}
        if resume and resume["extracted_json"]:
            try:
                extracted = json.loads(resume["extracted_json"])
            except json.JSONDecodeError:
                extracted = {}
        return render_template(
            "resume.html",
            resume=resume,
            extracted=extracted,
            profile=g.repo.profile_for_user(g.user["id"]),
        )

    @app.post("/resume/confirm")
    @login_required
    def confirm_resume():
        validate_csrf()
        try:
            g.repo.confirm_resume_extraction(
                g.user["id"],
                int(request.form["resume_id"]),
                request.form.get("confirmed_resume_summary", ""),
                request.form.get("skills", ""),
            )
            flash("Confirmed resume details saved to Rahel's profile.", "success")
        except (PermissionError, ValueError) as exc:
            flash(str(exc), "error")
        return redirect(url_for("resume_upload"))

    @app.route("/job-search-settings", methods=["GET", "POST"])
    @login_required
    def job_search_settings():
        if request.method == "POST":
            validate_csrf()
            g.repo.update_search_settings(
                g.user["id"],
                job_titles=request.form.get("job_titles", ""),
                acceptable_locations=request.form.get("acceptable_locations", ""),
                minimum_pay=parse_float(request.form.get("minimum_pay")),
                employment_types=request.form.get("employment_types", ""),
                search_keywords=request.form.get("search_keywords", ""),
                remote_ok=bool(request.form.get("remote_ok")),
            )
            flash("Job-search settings saved.", "success")
            return redirect(url_for("job_search_settings"))
        return render_template(
            "job_search_settings.html",
            settings=g.repo.search_settings(g.user["id"]),
            sources=g.repo.list_job_sources(g.user["id"]),
        )

    @app.post("/job-sources")
    @login_required
    def add_job_source():
        validate_csrf()
        provider = request.form.get("provider", "")
        board_identifier = request.form.get("board_identifier", "").strip()
        if provider not in {"greenhouse", "lever", "lever_eu"}:
            flash("Choose Greenhouse or Lever.", "error")
        elif not board_identifier:
            flash("Enter the employer board identifier.", "error")
        else:
            g.repo.add_job_source(g.user["id"], provider, board_identifier, request.form.get("display_name", ""))
            flash("Job board saved.", "success")
        return redirect(url_for("job_search_settings"))

    @app.post("/jobs/find")
    @login_required
    def find_jobs():
        validate_csrf()
        result = g.repo.fetch_jobs_from_sources(g.user["id"])
        for error in result["errors"]:
            flash(error, "error")
        flash(
            f"Found {result['found']} postings. Added {result['created']}, updated {result['updated']}, "
            f"duplicates {result['duplicates']}, stale {result['stale']}.",
            "success",
        )
        return redirect(url_for("job_feed"))

    @app.route("/jobs/import", methods=["GET", "POST"])
    @login_required
    def import_jobs():
        if request.method == "POST":
            validate_csrf()
            result = parse_job_json(request.form.get("jobs_json", ""))
            created = 0
            updated = 0
            for job in result.jobs:
                _, was_created = g.repo.upsert_job(g.user["id"], job)
                created += int(was_created)
                updated += int(not was_created)
            for error in result.errors:
                flash(error, "error")
            flash(f"Imported {created} new jobs and updated {updated}.", "success")
            return redirect(url_for("job_feed"))
        return render_template("import_jobs.html")

    @app.get("/jobs")
    @login_required
    def job_feed():
        return render_template("job_feed.html", jobs=g.repo.list_jobs(g.user["id"]), metrics=g.repo.job_feed_metrics(g.user["id"]))

    @app.post("/jobs/<int:job_id>/prepare")
    @login_required
    def prepare_job(job_id: int):
        validate_csrf()
        try:
            draft_id = g.repo.prepare_job(g.user["id"], job_id)
            flash("Draft prepared for review.", "success")
            return redirect(url_for("review_detail", draft_id=draft_id))
        except (PermissionError, ValueError) as exc:
            flash(str(exc), "error")
            return redirect(url_for("job_feed"))

    @app.get("/review")
    @login_required
    def review_queue():
        return render_template("review_queue.html", drafts=g.repo.list_review_queue(g.user["id"]))

    @app.route("/review/<int:draft_id>", methods=["GET", "POST"])
    @login_required
    def review_detail(draft_id: int):
        if request.method == "POST":
            validate_csrf()
            action = request.form.get("action")
            try:
                if action == "save":
                    g.repo.update_draft_text(
                        g.user["id"],
                        draft_id,
                        request.form.get("resume_summary", ""),
                        request.form.get("cover_letter", ""),
                        request.form.get("form_answers", ""),
                    )
                    flash("Draft saved.", "success")
                elif action == "approve":
                    if request.form.get("confirm_count") != "1":
                        raise ValueError("Type 1 to confirm approval of this one application.")
                    g.repo.approve_draft(g.user["id"], draft_id, "Approved 1 application", 1)
                    flash("Application approved. It has not been submitted.", "success")
                elif action == "reject":
                    g.repo.reject_draft(g.user["id"], draft_id, request.form.get("note", ""))
                    flash("Application rejected.", "success")
                elif action == "open":
                    url = g.repo.open_for_manual_submission(g.user["id"], draft_id)
                    flash("Open the employer page and submit manually only if everything looks right.", "success")
                    return render_template("manual_open.html", url=url, draft=g.repo.get_draft(g.user["id"], draft_id))
                elif action == "submitted":
                    g.repo.confirm_manual_submission(g.user["id"], draft_id, True, request.form.get("note", ""))
                    flash("Manual submission recorded.", "success")
                    return redirect(url_for("application_history"))
                elif action == "not_submitted":
                    g.repo.confirm_manual_submission(g.user["id"], draft_id, False, request.form.get("note", ""))
                    flash("Marked as not submitted.", "success")
                else:
                    raise ValueError("Unknown review action.")
            except (PermissionError, ValueError) as exc:
                flash(str(exc), "error")
            return redirect(url_for("review_detail", draft_id=draft_id))
        draft = g.repo.get_draft(g.user["id"], draft_id)
        if not draft:
            flash("Draft not found.", "error")
            return redirect(url_for("review_queue"))
        return render_template("review_detail.html", draft=draft)

    @app.get("/history")
    @login_required
    def application_history():
        return render_template("history.html", rows=g.repo.application_history(g.user["id"]))

    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        if request.method == "POST":
            validate_csrf()
            g.repo.update_account_settings(
                g.user["id"],
                parse_int(request.form.get("default_daily_limit"), default=5, minimum=1, maximum=50),
                bool(request.form.get("pause_all")),
                bool(request.form.get("high_contrast")),
                bool(request.form.get("large_text")),
            )
            flash("Settings saved.", "success")
            return redirect(url_for("settings"))
        return render_template("settings.html", settings=g.repo.account_settings(g.user["id"]))

    return app


def parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value or default)
    except ValueError:
        parsed = default
    return max(minimum, min(maximum, parsed))


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
