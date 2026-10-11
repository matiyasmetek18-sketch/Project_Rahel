from __future__ import annotations

import json

from job_assistant.repository import Repository


def csrf_from(html: str) -> str:
    return html.split('name="csrf_token" value="')[1].split('"')[0]


def sign_in(client, repo: Repository, username: str = "rahel") -> None:
    repo.create_user(username, f"{username}@example.com", "another-safe-password")
    html = client.get("/signin").get_data(as_text=True)
    token = csrf_from(html)
    response = client.post(
        "/signin",
        data={"username": username, "password": "another-safe-password", "csrf_token": token},
    )
    assert response.status_code == 302


def test_required_pages_render_for_signed_in_user(client, repo: Repository):
    sign_in(client, repo)
    for path, expected in [
        ("/dashboard", "Dashboard"),
        ("/profile", "Profile"),
        ("/credentials", "Credentials"),
        ("/resume", "Resume"),
        ("/job-search-settings", "Job-search settings"),
        ("/jobs", "Job feed"),
        ("/review", "Review queue"),
        ("/history", "Application history"),
        ("/settings", "Settings"),
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert expected in response.get_data(as_text=True)


def test_job_import_prepare_review_flow(client, repo: Repository):
    sign_in(client, repo)
    html = client.get("/profile").get_data(as_text=True)
    token = csrf_from(html)
    client.post(
        "/profile",
        data={
            "csrf_token": token,
            "full_name": "Rahel Example",
            "phone": "555-0100",
            "city": "Lynnwood",
            "state": "WA",
            "zip_code": "98036",
            "acceptable_cities": "Lynnwood",
            "confirmed_resume_summary": "Experienced caregiver.",
        },
    )
    html = client.get("/jobs/import").get_data(as_text=True)
    token = csrf_from(html)
    payload = json.dumps(
        [
            {
                "source_site": "manual_import",
                "external_id": "care-1",
                "title": "Caregiver",
                "company": "Example Care",
                "city": "Lynnwood",
                "state": "WA",
                "url": "https://example.test/apply",
                "required_fields": ["name", "email", "phone", "resume"],
            }
        ]
    )
    response = client.post("/jobs/import", data={"csrf_token": token, "jobs_json": payload}, follow_redirects=True)
    assert "Imported 1 new jobs" in response.get_data(as_text=True)
    html = client.get("/jobs").get_data(as_text=True)
    token = csrf_from(html)
    response = client.post("/jobs/1/prepare", data={"csrf_token": token}, follow_redirects=True)
    body = response.get_data(as_text=True)
    assert "Application type" in body
    assert "easy apply" in body


def test_logout_requires_csrf(client, repo: Repository):
    sign_in(client, repo)
    assert client.post("/signout").status_code == 400


def test_invalid_settings_limit_falls_back_without_server_error(client, repo: Repository):
    sign_in(client, repo)
    html = client.get("/settings").get_data(as_text=True)
    token = csrf_from(html)
    response = client.post(
        "/settings",
        data={"csrf_token": token, "default_daily_limit": "not-a-number", "high_contrast": "1", "large_text": "1"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Settings saved" in response.get_data(as_text=True)

