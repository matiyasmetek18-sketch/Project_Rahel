# Local Job Application Assistant

This is a local-first job-application assistant for Matiyas and Rahel. It stores each person's profile, credentials, resume location, job-search settings, imported jobs, review queue, and application history separately. The app is designed to run on the user's own computer and binds to `127.0.0.1` by default.

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

Open `http://127.0.0.1:5000` in your browser.

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

## What Milestone 2 Includes

- A complete server-rendered Flask website with sign in, dashboard, profile, credentials, resume, job-search settings, job feed, review queue, application history, and settings pages.
- A permitted offline job import workflow using pasted JSON.
- Per-account job deduplication by source and external id.
- Application preparation from stored profile data only.
- A server-side application state machine: `discovered -> prepared -> pending_review -> approved -> opened_for_manual_submission -> submitted / not_submitted`.
- Rejection and failure states.
- Manual-only submission flow. The app can open an employer link, but it never claims the application was submitted until the user confirms it.
- Pause-all and daily-limit enforcement before opening manual applications.
- Accessible, high-contrast templates with large text, large controls, visible focus, and mobile-friendly layout.

## Uploading A Resume

1. Sign in.
2. Open **Resume**.
3. Upload a PDF or DOCX file no larger than 5 MB.
4. Open **Profile** and write a confirmed resume summary.

The app stores the file under the private resume folder and does not commit it to git.

## Importing Jobs

Milestone 2 uses manual JSON import instead of scraping. Open **Job Feed**, choose **Import jobs**, and paste data like:

```json
[
  {
    "source_site": "manual_import",
    "external_id": "care-1",
    "title": "Caregiver",
    "company": "Example Care",
    "city": "Lynnwood",
    "state": "WA",
    "url": "https://example.test/apply",
    "description": "Caregiving transfer support companionship",
    "required_fields": ["name", "email", "phone", "resume"]
  }
]
```

This is deliberate: it gives the project a working job-feed workflow without violating job-site terms or relying on network access during tests.

## Reviewing Applications

1. Open **Job Feed**.
2. Choose **Prepare for review** on a job.
3. Open the draft in **Review Queue**.
4. Read the score, reasons, missing questions, resume summary, cover letter, and form answers.
5. Edit anything needed.
6. Type `1` to approve that one application.
7. Choose **Open to submit manually**.
8. Submit on the employer site yourself.
9. Return to the app and choose whether it was submitted or not submitted.

Approval is not submission. Opening the page is not submission. Only the user's final confirmation records a submitted application.

## Adding A New Job Source

Job sources must start disabled. Before writing an adapter, check the site's terms of service and robots.txt. If either is not verified, the adapter docstring must include `TODO: verify terms` and the app must not automate submissions for that site.

Permitted adapters may read forms and classify postings. If a form needs anything outside stored, confirmed profile data plus a resume upload, the posting is manual. For manual postings, the app prepares information and opens the page for the user to submit.

## Decisions And Tradeoffs

- **Flask instead of a heavier framework:** Flask keeps the learning surface small for a junior CS student while still supporting secure sessions and server-rendered pages.
- **SQLite for local storage:** SQLite is built into Python and is enough for a local app used by two people.
- **bcrypt for passwords:** bcrypt is a standard salted password-hashing library with a small dependency footprint.
- **Manual JSON import before adapters:** Milestone 2 needs a real feed, but scraping without terms review would be unsafe. JSON import is simple, testable, and honest about where data came from.
- **No background automation yet:** Milestones 1 and 2 focus on safe data handling and manual review before touching third-party submission flows.
- **Private resume folder:** Uploaded resumes are stored under `private/`, which is git-ignored, because resumes contain personal data.
- **Server-side state machine:** Application status changes live in repository methods so tests can enforce the safety rules without depending on browser behavior.

## Audit Notes

The Milestone 1 audit verified password hashing, sessions, CSRF on forms, account isolation, resume upload validation, scoring, drafting, and approval ownership tests. It also found that Milestone 1 documentation described future website behavior that was not yet implemented. Milestone 2 adds the missing website pages, job import/feed workflow, review queue, application history, settings, and manual submission state transitions.

## Current Limitations

- Resume extraction is not implemented; users manually confirm the resume summary.
- There is no live job API integration yet.
- There are no automated submission adapters.
- The app is intended for local use on `127.0.0.1`.
- Accessibility has been designed into the templates, but it still deserves human screen-reader testing.

## Questions Before Milestone 3

1. Which job sites are permitted for the first adapter?
2. What daily limits should each account use for each site?
3. Will this stay only on the user's computer, or should it be hosted publicly later?
