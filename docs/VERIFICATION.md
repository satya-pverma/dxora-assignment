# Verification and live demonstration runbook

## Recorded status

Status as of 17 November 2026. The 196-test result below was supplied from the
developer's normal Windows PowerShell terminal, running Python 3.13.17. It was
not a successful live publishing or LLM run. CI for the final PR must be checked
separately after pushing it.

| Check | Evidence | Status |
| --- | --- | --- |
| Full regression suite | `196 passed, 1 warning in 1.02s` | Passed in the developer's terminal |
| Ruff | `All checks passed!` | Passed in the same terminal |
| Compilation, OpenAPI and example schemas | Local static checks in the editing session | Passed |
| Live website HTTP/TLS/SNI | No recorded external fetch | Pending |
| Live `/link-analysis` | No configured OpenAI key or actual response | Pending |
| Actual five-platform publication | No configured publishing credentials or posted URLs | Pending |
| Model quality, cost and latency benchmark | Comparison and estimates exist; no live measurements | Pending |
| Sanitized screenshots/logs of live behavior | None recorded | Pending |

The one warning concerns deprecated HTTPX use in Starlette TestClient. Tests
still pass; the production clients use HTTPX directly. A dependency migration is
separate work and has not been silently applied to this submission.

## Reproduce local checks

Run from the repository root. To reproduce the tested Windows package versions,
install `requirements-tested.txt` into a fresh Python 3.13 environment. The
unversioned-range `requirements-dev.txt` remains available for compatibility
checks; do not describe a fresh range-based install as an identical environment.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-tested.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m compileall -q app scripts tests
.\.venv\Scripts\python.exe -m scripts.check_credentials
git diff --check
```

The credential command prints field names and presence only, makes no network
requests, and does not prove that credentials work. `--strict` exits 1 when any
service is missing required fields, useful before a complete live demo. It exits
2 on invalid configuration without displaying secret input values. Unit tests
need no credentials and use mocked DNS/HTTP. Tests never publish messages.

CI checks the declared Python 3.11 range-based dependencies on Linux and the
tested version snapshot with Python 3.13 on Windows. Its results are not recorded
as passed until the actual jobs complete.

## Configure locally

Copy `.env.example` to `.env` only if `.env` does not already exist. Fill credentials
locally using the [README configuration tables](../README.md). Never paste tokens
into chat, source files, PR descriptions, terminal transcripts, or screenshots.

The application does not create accounts, obtain OAuth tokens, add a bot as an
administrator, or grant publishing rights. Those prerequisites must already be
established on your owned test destinations. Keep the repository public while
keeping all credentials private.

For the first startup, bind to loopback in a terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 4000
```

The assignment's `--host 0.0.0.0` command also works when needed. No inbound API
authentication is implemented, so choose the listening interface deliberately.
Keep this assignment service local to the intended test environment.

## Read-only checks before publication

1. Open `http://localhost:4000/docs` and check the request/response contracts.
2. Run `Invoke-RestMethod http://localhost:4000/health`; expect `status=ok`.
3. Send a request with a missing URL or a posting message without a CTA; expect
   HTTP 422 and no provider call. Use the documented sample request shapes.
4. To verify extraction without an LLM call, run the following. It fetches the
   public website but does not publish or use model credits:

```powershell
.\.venv\Scripts\python.exe -c "import asyncio; from app.services.website_extractor import WebsiteExtractor; result=asyncio.run(WebsiteExtractor().extract('https://example.com')); print(result.model_dump_json(indent=2))"
```

Record the returned final URL and cleaned content or the exact safe error code.
Do not disable TLS verification or SSRF checks to make a restricted site pass.

## Live analysis evidence

Choose a public business website with useful service content, then call
`POST /link-analysis` once using its URL. This uses the configured OpenAI account
and incurs API charges. Preserve a sanitized request and complete response.

Check all five sections, query count/platform coverage, source quotes, inference
labels, warnings, truncation, provider/model and token usage. Confirm that quote
matches support the service interpretations; substring validation alone is not
a factual quality guarantee. Compare results with the actual page manually.

For cost evidence, record the actual billed input/output usage and dated provider
rates. Include billable reasoning and any retries when present. For latency,
record the observed elapsed time, run count, and environment; one run cannot
support percentile or best-model claims. Follow the evaluation plan in
[integration research](INTEGRATION_RESEARCH.md) for a cross-model benchmark.
If only one model is tested, keep the other comparisons explicitly estimated.

## Live posting evidence

Before any live `/posting` request, agree the exact message/CTA and the five owned
destinations. A configured request publishes publicly and may not be safe to
repeat. The application neither deduplicates repeated requests nor retries writes.

1. Check account and posting permission prerequisites for each platform.
2. Ensure `POSTING_PLATFORMS` names only the intended destinations for this run.
3. Submit the agreed message once, with at most 200 characters and one HTTP(S) CTA.
4. Save the full result: per-platform status, posted URL, UTC date/time,
   public-access result and error. Keep credentials out of saved evidence.
5. Open each posted URL anonymously and confirm identity and exact content. If a
   widget, login challenge, compression or indexing delay prevents automatic
   visibility verification, record that limit; do not turn a false flag into an
   unqualified success claim.
6. For partial-failure evidence, a local test-only configuration can intentionally
   omit one credential. Restore it afterward. Remember that the other configured
   adapters still publish; choose the message and destinations for that separate
   run too. Mocked partial failures already have unit-test coverage.
7. For timeouts or uncertain outcomes, inspect the destination before retrying.
   Do not resubmit automatically, since the first write may have succeeded.

The required demonstration is actual publishing through all five adapters, not
five successful mock fixtures. Record genuine restrictions/failures if account
access prevents a complete demo; do not fabricate URLs or timestamps.

## Evidence files

The files under `docs/examples/` are synthetic contract examples only. They are
not live evidence. Raw local run outputs belong in the ignored `evidence-local/`
directory. Review and sanitize copies before deliberately committing them under
`docs/evidence/`; include public requests/responses, screenshots or logs that a
reviewer can reproduce. Remove tokens, authorization headers, bot paths, account
secrets, and unrelated private details. Store applicant contact details in the
submission email rather than the public repository.
