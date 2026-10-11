# Project Rahel

Project Rahel is a local-first Flask/SQLite caregiver job-search assistant for Rahel. It helps find caregiver postings, score them against Rahel's confirmed profile data, prepare truthful application drafts, and track manual submission outcomes.

The app stays local and binds to `127.0.0.1` by default. It does not automate real submissions in the current milestone.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m job_assistant.cli init-db
.venv/bin/python -m job_assistant.cli create-user rahel rahel@example.com
```

Run the website:

```bash
.venv/bin/python -m job_assistant.web
```

Open `http://127.0.0.1:5000`.

Run tests:

```bash
.venv/bin/pytest
```

## Current Functionality

- Secure sign-in with bcrypt password hashing, secure session cookies, and CSRF protection.
- Rahel profile, credentials, work history, résumé upload, job preferences, job feed, review queue, application history, and settings.
- Guided onboarding page for profile readiness, résumé confirmation, and public employer board setup.
- Private résumé storage under `private/`.
- PDF/DOCX text extraction with user confirmation before saving extracted skills or summary data.
- Manual JSON import remains available for permitted postings.
- Live read-only job discovery from configured employer boards: Greenhouse Job Board API and Lever Postings API.
- Deterministic caregiver job scoring with explainable reasons, shown directly in the job feed before drafts are prepared.
- Feed-level discovery metrics for valid listings, relevant listings, likely eligibility, unknown qualifications, and stale postings.
- Stale posting detection when a previously fetched job no longer appears in a configured employer feed.
- Manual application review, approval, open-to-submit, and user-confirmed outcome tracking.
- Visible audit events on review and history pages.
- Pause-all and daily-limit safeguards.
- Offline tests with fictional data and mocked external sources.

## Finding Jobs

1. Sign in as Rahel.
2. Open **Onboarding**.
3. Complete profile, preferences, résumé confirmation, and credentials.
4. Add the recommended public boards or open **Search Settings** and add employer boards:
   - Greenhouse: use the public board token from the employer's Greenhouse board.
   - Lever: use the public Lever site name.
5. Click **Find Jobs**.
6. Open **Job Feed** to inspect ranked postings, match explanations, missing information, and stale-listing warnings.

The adapters only read public job postings. They do not submit applications.

### Milestone 4 Validation

Read-only validation on October 10, 2026 used genuine public ATS feeds:

- Greenhouse `bayada`: 2,545 active postings, 12 Washington/remote postings, 213 caregiver-relevant postings, 0 likely eligible for the fictional profile. Most blockers were missing licensed nursing credentials.
- Lever `mylaurelhealth`: 4 active postings, 4 Washington/remote postings, 1 caregiver-relevant and likely eligible posting: Care Navigator in Seattle at $22/hour.
- Lever `distro`: 165 active postings, 10 Washington/remote postings, 25 caregiver-relevant postings, 0 likely eligible for the fictional profile.

Duplicate rate was 0 across these feeds during validation. Source failures were 0 after adding an explicit CA bundle for HTTPS verification. The validation profile was fictional and did not use real applicant data.

## Résumé Intelligence

Upload a PDF or DOCX résumé from the **Resume** page. The app extracts candidate information such as skills, education, certifications, and relevant experience. Extracted text is treated as untrusted until Rahel reviews and confirms it.

No qualification is considered verified just because it appears in an uploaded document.

## Application Workflow

The current workflow is:

`Discover -> Normalize -> Deduplicate -> Match -> Prepare -> Review -> Approve -> Open employer page -> Rahel confirms submitted/not submitted -> Track`

Approval is not submission. Opening the employer page is not submission. Only Rahel's confirmation records a submitted application.

Drafts are deterministic and editable. They use only confirmed profile data, confirmed résumé summary, and saved work history. Unknown required fields remain questions before approval.

## Agent Architecture

The code includes Milestone 3A scaffolding for:

- **Discovery Agent:** read-only job-board discovery from permitted APIs.
- **Matching Agent:** deterministic caregiver match scoring.
- **Application Agent:** truthful draft preparation from confirmed data.
- **Verification Agent:** future pre-submission safety checks.
- **Tracking Agent:** audit trail and duplicate prevention.
- **Browser Agent:** intentionally not implemented yet.

Security-critical decisions, authorization, state transitions, and eligibility checks remain deterministic Python code. AI model use is reserved for future language-understanding tasks and must not receive real applicant information without explicit authorization.

## Model Benchmarking

`job_assistant/model_benchmark.py` defines a reproducible fictional caregiver benchmark for comparing future model providers. Real provider integration is not implemented yet. A model must be evaluated on structured requirement extraction, hallucination resistance, latency, cost, and privacy before use with real applicant data.

## Safety Rules

- Never fabricate credentials, employment history, dates, pay, licenses, or statistics.
- Never answer sensitive or voluntary demographic questions automatically.
- Never bypass CAPTCHA, login, MFA, bot checks, or rate limits.
- Never submit applications through sites whose terms prohibit automation.
- Store API keys only in environment variables.
- Keep `.env`, local databases, résumés, cookies, and browser session files out of git.

## Automation Boundary

See [docs/automation.md](docs/automation.md). Real browser-assisted form filling and API submission are disabled. Greenhouse and Lever are used only for permitted public read-only discovery. The MVP opens employer application pages for Rahel and records the outcome she confirms.

## Current Limitations

- Browser-assisted form filling is not implemented.
- Autonomous submission is not implemented.
- Greenhouse and Lever integrations are read-only discovery adapters.
- Résumé extraction is heuristic and must be confirmed by Rahel.
- Accessibility has structural support but still needs human screen-reader review.

## Before Browser-Assisted Submission

Rahel must approve:

1. Which employers and integrations are allowed.
2. Which job types, locations, pay ranges, and daily limits are allowed.
3. Whether browser-assisted filling may operate while she is present.
4. Whether any integration explicitly permits automated submission.
5. What information must always require individual review.
