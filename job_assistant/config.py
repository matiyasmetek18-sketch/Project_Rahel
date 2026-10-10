from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")
    DATABASE = Path(os.environ.get("JOB_ASSISTANT_DB", BASE_DIR / "instance" / "job_assistant.sqlite"))
    RESUME_DIR = Path(os.environ.get("JOB_ASSISTANT_RESUME_DIR", BASE_DIR / "private" / "resumes"))
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    DEFAULT_DAILY_LIMIT = 5

