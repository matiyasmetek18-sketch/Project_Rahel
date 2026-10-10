# Job Application Assistant Rules

This project is a local-first job-application assistant for two separate accounts: Matiyas and Rahel.

## Commands

- Create a virtual environment: `python3 -m venv .venv`
- Install dependencies: `.venv/bin/pip install -r requirements.txt`
- Initialize the database: `.venv/bin/python -m job_assistant.cli init-db`
- Create a user: `.venv/bin/python -m job_assistant.cli create-user matiyas matiyas@example.com`
- Run the website locally: `.venv/bin/python -m job_assistant.web`
- Run tests: `.venv/bin/pytest`

## Hard Rules

1. No application may be submitted without a recorded per-application approval in the database.
2. Automate submission only on explicit allowlisted sites. Each adapter docstring must record terms-of-service and robots.txt checks. Unverified adapters must say `TODO: verify terms` and remain disabled.
3. Never bypass CAPTCHAs, logins, two-factor prompts, bot checks, or rate limits. Stop, log the event, and ask the user to act.
4. Never store third-party site passwords.
5. Never fabricate credentials, employers, dates, pay, or statistics. Unknown required fields become user questions before approval.
6. Enforce a daily application limit per site and per account, defaulting to 5.
7. Do not answer voluntary demographic or sensitive questions automatically.
8. Store no SSN, date of birth, bank, health, or background-check data. Store resume files privately and out of git. Never log full profile contents. Mask certificate numbers.
9. Read secrets from environment variables only. Keep `.env`, `data/`, and resume files out of git.
10. Keep dependencies minimal and pinned.

## Milestone Status

- Milestone 1: foundations in progress/completed in this repository.
- Milestone 2: full website pages and manual submission flow.
- Milestone 3: one verified permitted easy-apply adapter, selected by the user after terms review.

