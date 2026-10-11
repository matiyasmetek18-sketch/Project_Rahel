# Automation Support

Project Rahel supports read-only job discovery and manual-assisted applications.

## Supported

- Greenhouse Job Board API GET endpoints for public postings.
- Lever Postings API GET endpoints for public postings.
- Deterministic local matching, draft preparation, review, approval, opening the employer URL, and user-confirmed outcome tracking.

## Not Enabled

- Browser-assisted completion of real employer forms.
- API-based application submission.
- Fully autonomous submission.

## Evaluation

Greenhouse and Lever document application submission APIs for custom career sites, and Lever documents rate limits and spam mitigation requirements. Greenhouse-hosted forms may include reCAPTCHA and email verification. This project does not have employer authorization to operate a custom application site or automate hosted forms for Rahel.

Because no employer integration has been demonstrably authorized for automated completion, the MVP keeps real submissions manual. Any future adapter must document employer permission, terms review, rate-limit behavior, CAPTCHA/MFA stop conditions, explicit per-application approval, and local fictional-form tests before it can be enabled.
