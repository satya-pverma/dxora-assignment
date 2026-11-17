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

Foundation is published on `main`. Integration research is documented in
[INTEGRATION_RESEARCH.md](INTEGRATION_RESEARCH.md); model benchmarks and live
publishing verification remain implementation tasks.

Website extraction is implemented as an internal service with simulated-network
tests. Local Windows validation with Python 3.13.17 passed all 42 tests and Ruff;
live TLS/SNI verification remains pending. The extraction PR is merged.

The merged analysis milestone implements `/link-analysis` with one OpenAI structured-output
call, validated analysis schemas, evidence warnings, provider error handling,
and mocked API tests. Live model benchmarking, cross-provider fallback, and
caching remain deferred and must not be described as completed.
Local Windows verification with Python 3.13.17 passed all 75 tests and Ruff.
Compilation and OpenAPI generation also passed. Live provider verification,
model benchmarks, and HTTPS/SNI verification remain pending.

The current posting milestone adds `/posting` validation, a shared adapter
contract, internal configurable selection, independent timeouts/failure results,
and tests with fake adapters. Default adapters explicitly report unavailable
integrations; this is not completion of the five live integrations. Local Windows
verification with Python 3.13.17 passed all 119 tests and Ruff. Compilation,
OpenAPI generation, and local documentation links also passed. The first three
real adapters follow this PR; no live publication has been demonstrated yet.

1. Establish this repository and record the implementation plan.
2. PR: FastAPI foundation, environment configuration, tests, and CI.
3. PR: Research five publishing APIs and at least three LLM models using official
   documentation. Record authentication requirements, current pricing, limitations,
   model recommendation, fallback, estimated tokens/cost, and cost optimizations.
4. PR: URL validation, SSRF protection including redirects and DNS resolution,
   bounded website fetching, HTML extraction, and cleaned content.
5. PR: LLM integration and validated `/link-analysis` response with competitor
   analysis, exactly five search queries covering the supported platforms, SEO
   recommendations, top five services, and target audiences. Clearly mark
   inferences and unverified competitor suggestions; never invent search volumes.
6. PR: `/posting` validation (maximum 200 characters, exactly one valid CTA URL),
   platform adapters, internal selection, and independent failure handling.
7. PR: First three actual publishing integrations.
8. PR: Two remaining publishing integrations and partial-failure verification.
9. PR: Final checks, README, sample requests/responses, sanitized demonstration
   evidence, and submission checklist.

Tests accompany each implementation PR. Mocked tests are not evidence of actual
publishing. Live demonstrations require configured accounts and an explicitly
authorized message and destinations. Research credentials and publishing access
early; do not count a non-publishing LLM call as a publishing integration.

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
