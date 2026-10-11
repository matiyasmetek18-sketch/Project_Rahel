# Project Rahel Rules

This project is a local-first caregiver job-search assistant for Rahel.

## Commands

- Create a virtual environment: `python3 -m venv .venv`
- Install dependencies: `.venv/bin/pip install -r requirements.txt`
- Initialize the database: `.venv/bin/python -m job_assistant.cli init-db`
- Create Rahel's local account: `.venv/bin/python -m job_assistant.cli create-user rahel rahel@example.com`
- Run the website locally: `.venv/bin/python -m job_assistant.web`
- Run tests: `.venv/bin/pytest`

## Hard Rules

1. Do not assume Rahel has a license, certificate, language, availability, employer history, or credential until she confirms it.
2. No application may be submitted without explicit authorization rules and an auditable record.
3. Automated submission is disabled unless a future integration is explicitly allowlisted and terms-permitted.
4. Each adapter docstring must record its API/terms check. Unverified submission adapters must say `TODO: verify terms` and remain disabled.
5. Never bypass CAPTCHAs, logins, two-factor prompts, bot checks, or rate limits.
6. Never store third-party site passwords.
7. Never fabricate credentials, employers, dates, pay, statistics, or form answers.
8. Required fields with no confirmed value become questions for Rahel.
9. Enforce daily limits and pause-all behavior.
10. Do not answer voluntary demographic or sensitive questions automatically.
11. Store no SSN, date of birth, bank, health, or background-check data.
12. Store résumé files privately and out of git. Never log full profile contents. Mask certificate numbers.
13. Read secrets only from environment variables. Ignore `.env`, `data/`, local databases, résumé files, cookies, and browser session files.
14. Keep dependencies minimal and pinned.

## Current Milestone

Milestone 3A focuses on:

- Rahel-only caregiver job-search scope.
- Read-only live discovery through Greenhouse and Lever public job-posting APIs.
- Résumé PDF/DOCX extraction with user confirmation.
- Improved deterministic caregiver matching.
- Agent architecture scaffolding.
- No browser automation.
- No autonomous real submissions.

## Verified Behavior

- The website uses Flask and server-rendered Jinja templates with minimal JavaScript.
- Job discovery supports manual JSON import plus configured Greenhouse/Lever employer boards.
- Imported/fetched jobs are normalized and deduplicated per account by source and external id.
- The job feed ranks postings deterministically and explains match scores before applications are prepared.
- Jobs missing from later source fetches are marked stale instead of silently disappearing.
- Application drafts move through the server-side state machine: `discovered`, `prepared`, `pending_review`, `approved`, `opened_for_manual_submission`, `submitted`, `not_submitted`, `rejected`, and `failed`.
- Opening an employer page records only `opened_for_manual_submission`.
- Only Rahel can confirm a manual submission outcome.
- Pause-all and daily limits are enforced before opening a manual application page.
- Logout and all mutating forms require CSRF tokens.
- Tests are offline and use fictional data only.

## Current Limitations

- Browser-assisted form filling is not implemented.
- Autonomous submission is not implemented.
- AI provider integration is not implemented.
- Résumé extraction is heuristic and must be confirmed by Rahel.
- The UI is accessible and responsive, but it has not been tested with a screen reader by a human.
