# Implementation plan and current progress

Reviewed: **18 November 2026**.
Submission repository: https://github.com/satya-pverma/dxora-assignment

Source requirements:
- [Website analysis](https://github.com/chivoxai/practical-test/blob/main/link-analysis.md)
- [Multi-platform posting](https://github.com/chivoxai/practical-test/blob/main/python-post-message.md)

Both tasks are implemented in one FastAPI service. Work stays in the applicant's
repository, using feature branches and PRs; never write to the source repository.

| Milestone | Current status |
| --- | --- |
| FastAPI, configuration, CI and examples | Implemented; final CI result must be checked |
| Bounded website extraction and SSRF protections | Implemented; live HTTPS extraction passed |
| Five-section structured analysis | Implemented; Gemini gemini-3.1-flash-lite passed locally |
| Three-provider research and recommendation | Comparison present; selected recommendation aligned to Gemini; alternatives unbenchmarked |
| Posting validation and independent outcomes | Implemented and tested |
| Five platform adapters | Implemented; WordPress live test deferred |
| Live Mastodon, Bluesky, Tumblr and Telegram publishing | All four confirmed in one run |
| Anonymous visibility | Bluesky/Telegram passed; Mastodon/Tumblr manual checks pending |
| Dashboard, demo access and platform selection | Implemented; original message-only /posting preserved |
| Two analyses per minute per client IP | Implemented; single-process memory limit |
| IPv4 preference and Telegram diagnostics | Implemented; live connection and publication confirmed |
| Regression validation | Latest developer run: 255 passed; Ruff passed |
| Free deployment configuration | Prepared; public app/API/docs not deployed or verified |
| Submission evidence and personal application steps | Pending |

## Remaining sequence

1. Resolve WordPress account access and test the fifth destination (deferred by developer).
2. Check Mastodon/Tumblr post links anonymously and record any restrictions.
3. Save sanitized live request/response and test evidence in the repository.
4. Deploy the service, configure private secrets, and verify UI, API, /docs and demo access.
5. Check final PR CI and clean-environment setup, then complete submission checklist.

One working LLM integration is sufficient; the analysis assignment separately
requires research comparing at least three models/providers. Automatic fallback,
caching, multi-model benchmarks, durable publication deduplication and automatic
token refresh are not implemented. These are not claimed as completed.

## Deadlines and submission

Link analysis: **27 November 2026** (source spells it "27nd"); mandatory public
deployment, demo URL and /docs. Email subject: `Your Name - Python Practical Link Analysis test review`.
Posting: **22 November 2026**; email subject: `Your Name - Python Practical test review`.
Posting specifies 2-3 hours initially and four hours later; analysis specifies two
hours. Record actual effort honestly; no time-compliance claim is made here.

Both request a public repository, setup instructions, examples, screenshots/logs,
secret protection, and applicant profile verification. Personal contact details
belong in the submission email, not public code. See
[the submission checklist](SUBMISSION_CHECKLIST.md),
[verification record](VERIFICATION.md), and [deployment guide](DEPLOYMENT.md).
