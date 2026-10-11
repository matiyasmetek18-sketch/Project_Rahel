from __future__ import annotations

import json
from io import BytesIO

from job_assistant.repository import Repository


def csrf_from(html: str) -> str:
    return html.split('name="csrf_token" value="')[1].split('"')[0]


def login(client, username: str, password: str) -> None:
    html = client.get("/signin").get_data(as_text=True)
    token = csrf_from(html)
    response = client.post(
        "/signin",
        data={"username": username, "password": password, "csrf_token": token},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Dashboard" in response.get_data(as_text=True)


def logout(client) -> None:
    html = client.get("/dashboard").get_data(as_text=True)
    token = csrf_from(html)
    response = client.post("/signout", data={"csrf_token": token}, follow_redirects=True)
    assert response.status_code == 200
    assert "Sign in" in response.get_data(as_text=True)


def test_full_manual_application_acceptance_flow_and_account_isolation(client, repo: Repository):
    repo.create_user("rahel", "rahel@example.com", "another-safe-password")
    repo.create_user("matiyas", "matiyas@example.com", "a-very-safe-password")

    login(client, "rahel", "another-safe-password")

    html = client.get("/profile").get_data(as_text=True)
    token = csrf_from(html)
    response = client.post(
        "/profile",
        data={
            "csrf_token": token,
            "full_name": "Rahel Example",
            "phone": "555-0100",
            "city": "Lynnwood",
            "state": "WA",
            "zip_code": "98036",
            "skills": "caregiving, transfers",
            "availability": "weekdays",
            "transportation": "car",
            "minimum_hourly_pay": "22",
            "job_types": "home care",
            "acceptable_cities": "Lynnwood, Everett",
            "confirmed_resume_summary": "Experienced caregiver with confirmed profile details.",
            "employer": "Fictional Home Care",
            "title": "Caregiver",
            "start_date": "2024-01-01",
            "tasks": "Companionship and transfer support.",
        },
        follow_redirects=True,
    )
    assert "Profile saved" in response.get_data(as_text=True)

    html = client.get("/resume").get_data(as_text=True)
    token = csrf_from(html)
    response = client.post(
        "/resume",
        data={"csrf_token": token, "resume": (BytesIO(b"%PDF-1.7\nfictional resume"), "resume.pdf")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert "Resume uploaded" in response.get_data(as_text=True)

    html = client.get("/jobs/import").get_data(as_text=True)
    token = csrf_from(html)
    jobs = [
        {
            "source_site": "manual_import",
            "external_id": "care-acceptance",
            "title": "Caregiver",
            "company": "Example Care",
            "city": "Lynnwood",
            "state": "WA",
            "url": "https://example.test/apply",
            "description": "caregiving transfers companionship",
            "required_fields": ["name", "email", "phone", "resume"],
            "hourly_pay": 25,
        }
    ]
    response = client.post(
        "/jobs/import",
        data={"csrf_token": token, "jobs_json": json.dumps(jobs)},
        follow_redirects=True,
    )
    assert "Imported 1 new jobs" in response.get_data(as_text=True)
    assert "Score" not in response.get_data(as_text=True)

    html = client.get("/jobs").get_data(as_text=True)
    token = csrf_from(html)
    response = client.post("/jobs/1/prepare", data={"csrf_token": token}, follow_redirects=True)
    body = response.get_data(as_text=True)
    assert "Application type:" in body
    assert "easy apply" in body
    assert "/100" in body

    token = csrf_from(body)
    response = client.post(
        "/review/1",
        data={
            "csrf_token": token,
            "action": "save",
            "resume_summary": "Experienced caregiver with confirmed profile details.",
            "cover_letter": "Dear hiring team, fictional edited letter.",
            "form_answers": "",
        },
        follow_redirects=True,
    )
    assert "Draft saved" in response.get_data(as_text=True)

    token = csrf_from(response.get_data(as_text=True))
    response = client.post(
        "/review/1",
        data={"csrf_token": token, "action": "approve", "confirm_count": "1"},
        follow_redirects=True,
    )
    assert "has not been submitted" in response.get_data(as_text=True)

    token = csrf_from(response.get_data(as_text=True))
    response = client.post(
        "/review/1",
        data={"csrf_token": token, "action": "open"},
        follow_redirects=True,
    )
    assert "has not been submitted" in response.get_data(as_text=True)
    assert "https://example.test/apply" in response.get_data(as_text=True)

    html = client.get("/review/1").get_data(as_text=True)
    token = csrf_from(html)
    response = client.post(
        "/review/1",
        data={"csrf_token": token, "action": "submitted", "note": "Submitted manually by fictional user."},
        follow_redirects=True,
    )
    assert "submitted" in response.get_data(as_text=True)
    assert "Example Care" in response.get_data(as_text=True)

    logout(client)
    login(client, "matiyas", "a-very-safe-password")
    assert "Example Care" not in client.get("/jobs").get_data(as_text=True)
    assert "Example Care" not in client.get("/history").get_data(as_text=True)
    response = client.get("/review/1", follow_redirects=True)
    assert "Draft not found" in response.get_data(as_text=True)
