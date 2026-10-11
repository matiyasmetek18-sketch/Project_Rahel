from __future__ import annotations

from job_assistant.repository import Repository


def test_sign_in_sets_secure_session_cookie(client, app, repo: Repository):
    repo.create_user("rahel", "rahel@example.com", "a-very-safe-password")
    with client.get("/signin") as response:
        html = response.get_data(as_text=True)
    token = html.split('name="csrf_token" value="')[1].split('"')[0]
    response = client.post(
        "/signin",
        data={"username": "rahel", "password": "a-very-safe-password", "csrf_token": token},
    )
    assert response.status_code == 302
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_forms_reject_missing_csrf(client, repo: Repository):
    repo.create_user("rahel", "rahel@example.com", "a-very-safe-password")
    response = client.post("/signin", data={"username": "rahel", "password": "a-very-safe-password"})
    assert response.status_code == 400

