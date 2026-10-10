from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, g, redirect, render_template_string, request, session, url_for

from .config import Config
from .db import init_db
from .repository import Repository
from .resumes import ALLOWED_EXTENSIONS, stored_resume_path, validate_resume_upload
from .security import issue_csrf_token, login_required, validate_csrf

BASE_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }}</title>
  <style>
    body { font-family: system-ui, sans-serif; font-size: 20px; line-height: 1.5; margin: 0; color: #101418; background: #f8faf9; }
    main { max-width: 780px; margin: 0 auto; padding: 32px 20px; }
    label { display: block; margin-top: 18px; font-weight: 700; }
    input, textarea, button { font: inherit; padding: 12px; border: 2px solid #27343c; border-radius: 6px; width: 100%; box-sizing: border-box; }
    button { margin-top: 22px; background: #174f42; color: white; font-weight: 800; cursor: pointer; }
    nav a { margin-right: 16px; }
    .alert { padding: 12px; background: #fff3cd; border: 2px solid #8a6d00; border-radius: 6px; }
  </style>
</head>
<body>
<main>
  {% if g.user %}<nav><a href="{{ url_for('profile') }}">Profile</a><a href="{{ url_for('resume_upload') }}">Resume</a><a href="{{ url_for('signout') }}">Sign out</a></nav>{% endif %}
  {{ body|safe }}
</main>
</body>
</html>
"""


def page(title: str, body: str, **context):
    return render_template_string(BASE_HTML, title=title, body=render_template_string(body, **context))


def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["RESUME_DIR"]).mkdir(parents=True, exist_ok=True)
    init_db(app.config["DATABASE"])

    @app.before_request
    def load_user():
        g.repo = Repository(app.config["DATABASE"])
        user_id = session.get("user_id")
        g.user = g.repo.get_user(user_id) if user_id else None

    @app.context_processor
    def inject_csrf():
        return {"csrf_token": issue_csrf_token}

    @app.get("/")
    def index():
        if g.user:
            return redirect(url_for("profile"))
        return redirect(url_for("signin"))

    @app.route("/signin", methods=["GET", "POST"])
    def signin():
        error = ""
        if request.method == "POST":
            validate_csrf()
            user = g.repo.authenticate(request.form["username"], request.form["password"])
            if user:
                session.clear()
                session["user_id"] = user["id"]
                issue_csrf_token()
                return redirect(url_for("profile"))
            error = "Sign-in failed."
        return page(
            "Sign in",
            """
            <h1>Sign in</h1>
            {% if error %}<p class="alert">{{ error }}</p>{% endif %}
            <form method="post">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <label>Username <input name="username" required autocomplete="username"></label>
              <label>Password <input name="password" type="password" required autocomplete="current-password"></label>
              <button type="submit">Sign in</button>
            </form>
            """,
            error=error,
        )

    @app.get("/signout")
    def signout():
        session.clear()
        return redirect(url_for("signin"))

    @app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        saved = False
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
                acceptable_cities=request.form.get("acceptable_cities", ""),
                confirmed_resume_summary=request.form.get("confirmed_resume_summary", ""),
            )
            saved = True
        profile_data = g.repo.profile_for_user(g.user["id"])
        return page(
            "Profile",
            """
            <h1>Profile</h1>
            {% if saved %}<p class="alert">Saved.</p>{% endif %}
            <form method="post">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <label>Full name <input name="full_name" value="{{ profile.full_name }}"></label>
              <label>Phone <input name="phone" value="{{ profile.phone }}"></label>
              <label>City <input name="city" value="{{ profile.city }}"></label>
              <label>State <input name="state" value="{{ profile.state }}"></label>
              <label>ZIP <input name="zip_code" value="{{ profile.zip_code }}"></label>
              <label>Skills <input name="skills" value="{{ ', '.join(profile.skills) }}"></label>
              <label>Acceptable cities <input name="acceptable_cities" value="{{ ', '.join(profile.acceptable_cities) }}"></label>
              <label>Confirmed resume summary <textarea name="confirmed_resume_summary" rows="5">{{ profile.confirmed_resume_summary }}</textarea></label>
              <button type="submit">Save profile</button>
            </form>
            """,
            profile=profile_data,
            saved=saved,
        )

    @app.route("/resume", methods=["GET", "POST"])
    @login_required
    def resume_upload():
        message = ""
        if request.method == "POST":
            validate_csrf()
            uploaded = request.files.get("resume")
            if not uploaded or uploaded.filename == "":
                message = "Choose a PDF or DOCX resume."
            else:
                uploaded.seek(0, os.SEEK_END)
                size = uploaded.tell()
                uploaded.seek(0)
                ok, message = validate_resume_upload(uploaded.filename, size)
                if ok:
                    destination = stored_resume_path(Path(app.config["RESUME_DIR"]), g.user["id"], uploaded.filename)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    uploaded.save(destination)
                    content_type = ALLOWED_EXTENSIONS[destination.suffix.lower()]
                    g.repo.record_resume(g.user["id"], uploaded.filename, str(destination), content_type)
                    message = "Resume uploaded. Review and confirm extracted details before using them."
        return page(
            "Resume upload",
            """
            <h1>Resume upload</h1>
            {% if message %}<p class="alert">{{ message }}</p>{% endif %}
            <form method="post" enctype="multipart/form-data">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
              <label>Resume PDF or DOCX <input name="resume" type="file" accept=".pdf,.docx" required></label>
              <button type="submit">Upload resume</button>
            </form>
            """,
            message=message,
        )

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)

