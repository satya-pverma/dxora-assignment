# Implementation plan

Submission repository: https://github.com/satya-pverma/dxora-assignment

Source specifications:
- https://github.com/chivoxai/practical-test/blob/main/link-analysis.md
- https://github.com/chivoxai/practical-test/blob/main/python-post-message.md

## Scope and workflow

Plan assumes both tests will be completed in one FastAPI application. The source
documents do not explicitly establish whether both are required or alternatives.
Use focused branches, meaningful commits, and PRs into this repository's main.
Review checks before merging. Never push to the source specification repository.

## Milestones

| Step | Deliverable | Status |
| --- | --- | --- |
| 1 | Own repository and implementation plan | Completed |
| 2 | FastAPI foundation, environment configuration, tests, CI | Merged |
| 3 | Five publishing APIs and at least three LLM options, pricing and recommendations | Merged; benchmarks remain unmeasured |
| 4 | URL validation, SSRF protection, bounded website extraction | Merged; live TLS/SNI check pending |
| 5 | Structured `/link-analysis`, validation, inference labels, errors and tests | Merged; live model verification pending |
| 6 | `/posting` validation, internal selection, adapter contracts and failure isolation | Merged |
| 7 | Mastodon, Bluesky, WordPress.com adapters and mocked coverage | Merged; live accounts/publication unverified |
| 8 | Tumblr, Telegram, anonymous visibility checks and partial failures | Merged; live accounts/publication unverified |
| 9 | Final documentation, dependency snapshot, verification instructions and submission checklist | Handoff prepared; PR/CI and live evidence outstanding |
| 10 | Gemini provider, browser dashboard, and free deployment configuration | Local Gemini analysis confirmed by user; UI/deployment PR checks pending |

Latest supplied local verification: all **196 tests passed** and Ruff passed on
Windows/Python 3.13.17. Compilation, OpenAPI generation and documentation links
also passed local checks. The tested dependency snapshot and expanded CI are
part of the final handoff; actual new CI results must be checked after pushing.

See [integration research](INTEGRATION_RESEARCH.md),
[verification and live-evidence instructions](VERIFICATION.md), and
[submission checklist](SUBMISSION_CHECKLIST.md).

Mocked tests do not prove account access, public publication, model quality, or
model speed/cost. None of the six required provider credentials is configured in
the current local environment. Live demonstrations require those prerequisites
plus an explicitly authorized message and destinations. Automatic cross-provider
fallback, caching, token refresh, and model benchmarks have not been implemented
or measured and must not be presented as completed.

## Acceptance criteria

- Server runs on port 4000 with interactive docs at `/docs`.
- Analysis is based on fetched content, returns all required sections, validates
  LLM output, and handles invalid URLs, restricted sites, and provider errors.
- Posting returns actual per-platform status, posted URL, public-access result,
  date, time, and error; one failed platform does not stop the others.
- No credentials are committed. Include `.env.example` and reproducible setup.
- LLM research distinguishes measured performance from estimates.
- Include API examples and sanitized screenshots or logs demonstrating behavior.

## Submission notes

Deadline: 22 November 2026. Link analysis specifies two hours. Posting specifies
2–3 hours initially but four hours later; target the stricter budget and record
actual time honestly.

Documents request a public repository and email to hr@chivoxai.com with subject
`Your Name - Python Practical test review`, full name, repository URL, contact
number, location, and preferred discussion time. They also request following the
specified LinkedIn/Instagram accounts and providing applicant profile links.
Personal submission details belong in the submission, not public source files.
