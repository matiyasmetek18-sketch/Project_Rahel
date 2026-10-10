from __future__ import annotations

import secrets
from functools import wraps

import bcrypt
from flask import abort, g, redirect, request, session, url_for


def hash_password(password: str) -> bytes:
    if len(password) < 12:
        raise ValueError("Passwords must be at least 12 characters.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())


def verify_password(password: str, password_hash: bytes) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash)


def issue_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def validate_csrf() -> None:
    token = session.get("csrf_token")
    submitted = request.form.get("csrf_token")
    if not token or not submitted or not secrets.compare_digest(token, submitted):
        abort(400, "Invalid CSRF token.")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not getattr(g, "user", None):
            return redirect(url_for("signin"))
        return view(*args, **kwargs)

    return wrapped

