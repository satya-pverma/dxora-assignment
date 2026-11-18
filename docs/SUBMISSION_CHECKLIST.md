# Submission checklist

Reviewed against the source documents on **18 November 2026**.

| Task | Deadline | Email subject |
| --- | --- | --- |
| Link analysis | 27 November 2026 (source typo: 27nd) | Your Name - Python Practical Link Analysis test review |
| Posting | 22 November 2026 | Your Name - Python Practical test review |

Link analysis requires a public live deployment and API documentation URL.
Posting still has the earlier deadline; do not assume its date was extended.
The task time budgets are two hours for analysis and conflicting 2-3/four hours
for posting. Report actual effort honestly.

## Completed implementation and local verification

- [x] Own repository selected: https://github.com/satya-pverma/dxora-assignment
- [x] FastAPI /link-analysis and message-only /posting implemented.
- [x] Five analysis sections, structured validation, inference labels and URL/SSRF protection.
- [x] Three-provider comparison, estimated costs, selection rationale and alternative documented.
- [x] Live Gemini gemini-3.1-flash-lite analysis confirmed locally.
- [x] Five publishing adapters implemented with independent errors and public-access reporting.
- [x] Live publication confirmed for Mastodon, Bluesky, Tumblr and Telegram.
- [x] Automatic anonymous verification passed for Bluesky and Telegram in the observed run.
- [x] Browser UI, demo access, selected-destination endpoint and analysis rate limit implemented.
- [x] Latest developer verification: 255 tests passed and Ruff passed.
- [x] Setup files, environment template, synthetic API examples and Render configuration supplied.

## Remaining verification and delivery

- [ ] WordPress.com credentials/site configured and actual publication tested (deferred).
- [ ] Mastodon and Tumblr visibility checked anonymously; record restrictions if inconclusive.
- [ ] Assignment /posting demonstrated with all five server-enabled destinations.
- [x] Developer-supplied four-platform publishing response saved under docs/evidence.
- [ ] Analysis output, exact test request and deployment screenshots/logs archived.
- [ ] Public deployment completed; live UI, /link-analysis and /docs verified.
- [ ] Demo access key shared privately with reviewers and hosted credentials checked.
- [ ] Final GitHub CI jobs verified for the actual submitted commit.
- [ ] Public repository access and setup from a clean environment verified.
- [ ] Actual model usage/cost and run environment recorded where available; estimates remain labelled.
- [ ] Staged source and evidence checked for tokens, secret paths and private data; .env stays ignored.
- [ ] Required LinkedIn/Instagram follows completed and applicant profile links collected.
- [ ] Submission details, demo/repository links and preferred discussion time reviewed.
- [ ] Submission email sent personally before each applicable deadline.

Use [the verification runbook](VERIFICATION.md) and [deployment guide](DEPLOYMENT.md).
The examples under docs/examples are synthetic, not evidence of live publication.
Formal multi-model accuracy/speed benchmarks are not completed and are not required
to claim one functioning integration. Do not claim tested superiority.

## Email preparation

Send to `hr@chivoxai.com`, using the subject for the task being submitted above.
The analysis submission must include the live Demo Link; include /docs as well.
No submission email has been sent by the application or assistant.

```text
Hello,

Please find my Python practical-test submission below.

Full name: [Your full name]
Live demo: [Public deployment URL]
API documentation: [Public deployment URL]/docs
Public repository: https://github.com/satya-pverma/dxora-assignment
Contact number: [Your number]
Current location: [City, State]
Preferred discussion time: [Date, time and timezone]
LinkedIn profile: [Your profile URL]
Instagram profile: [Your profile URL]

Analysis model: Google Gemini gemini-3.1-flash-lite.
Verification evidence: [Repository evidence links]
Known limitations: [Accurate remaining limitations at submission time]

Thank you,
[Your full name]
```

Keep applicant contact details and demo keys out of public source and screenshots.
