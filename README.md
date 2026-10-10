# Local Job Application Assistant

This is a local-first job-application assistant for Matiyas and Rahel. It stores each person's profile, credentials, resume location, job-search settings, and application history separately. The app is designed to run on the user's own computer and binds to `127.0.0.1` by default.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m job_assistant.cli init-db
```

Create local accounts:

```bash
.venv/bin/python -m job_assistant.cli create-user matiyas matiyas@example.com
.venv/bin/python -m job_assistant.cli create-user rahel rahel@example.com
```

Run the website:

```bash
.venv/bin/python -m job_assistant.web
```

Run tests:

```bash
.venv/bin/pytest
```

## What Milestone 1 Includes

- A Flask app factory with secure local defaults.
- Passwords stored as bcrypt hashes.
- SQLite tables for users, profiles, credentials, resumes, jobs, drafts, approvals, and application events.
- CSRF protection on forms.
- Resume upload with PDF/DOCX allowlist and a 5 MB limit.
- Scoring, easy-apply classification, and draft generation from stored/confirmed data only.
- Tests for sign-in/session behavior, account separation, approval gate, daily limit, no-fabrication, upload limits, and easy-apply classification.

## Adding A New Job Source

Job sources must start disabled. Before writing an adapter, check the site's terms of service and robots.txt. If either is not verified, the adapter docstring must include `TODO: verify terms` and the app must not automate submissions for that site.

Permitted adapters may read forms and classify postings. If a form needs anything outside stored, confirmed profile data plus a resume upload, the posting is manual. For manual postings, the app prepares information and opens the page for the user to submit.

## Decisions And Tradeoffs

- **Flask instead of a heavier framework:** Flask keeps the learning surface small for a junior CS student while still supporting secure sessions and server-rendered pages.
- **SQLite for local storage:** SQLite is built into Python and is enough for a local app used by two people.
- **bcrypt for passwords:** bcrypt is a standard salted password-hashing library with a small dependency footprint.
- **No background automation yet:** Milestone 1 focuses on safe data handling and testable business rules before touching third-party sites.
- **Private resume folder:** Uploaded resumes are stored under `private/`, which is git-ignored, because resumes contain personal data.

## Questions Before Milestone 3

1. Which job sites are permitted for the first adapter?
2. What daily limits should each account use for each site?
3. Will this stay only on the user's computer, or should it be hosted publicly later?

