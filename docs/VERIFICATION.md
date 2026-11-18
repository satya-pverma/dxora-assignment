# Verification and live demonstration runbook

## Recorded status

The developer-supplied [live four-platform response](evidence/posting-live-2026-11-18.json)
is now saved in the repository. See [evidence context](evidence/README.md) for its
scope and the unresolved Mastodon/Tumblr visibility checks.

Status as of **18 November 2026**. Full-suite results were supplied by the
developer from Windows PowerShell, Python 3.13.17. Live results below distinguish
provider confirmation from anonymous visibility. They summarize observed runs in
the development session. The publishing response above is archived; analysis and
deployment artifacts remain pending.

| Check | Evidence | Status |
| --- | --- | --- |
| Full regression suite | Developer terminal: 255 passed, one warning | Passed |
| Ruff | Developer terminal: All checks passed | Passed |
| Compilation and OpenAPI | Local static checks during implementation | Passed |
| Live extraction | HTTPS example.com and portfolio extraction | Passed |
| Live analysis | Gemini gemini-3.1-flash-lite; five validated sections | Passed locally |
| Analysis latency | One observed response: 14.073 seconds end to end | Observation, not benchmark |
| Mastodon publication | Successful live result, post URL retained | Published; anonymous verification inconclusive |
| Bluesky publication | Successful live result with public_access=true | Published and automatically verified |
| Tumblr publication | Successful live result, post URL retained | Published; anonymous verification inconclusive |
| Telegram publication | Successful live result with public_access=true | Published and automatically verified |
| WordPress.com | Adapter/mock tests exist; account setup deferred after browser connectivity failure | Live test pending |
| Public deployment and hosted /docs | render.yaml and deployment guide supplied | Pending |
| Final GitHub CI and clean setup | Not independently confirmed on final commit | Pending |
| Token costs and multi-model accuracy/latency | Dated comparison exists; no archived usage/billing benchmark | Pending |
| Sanitized evidence files | Examples remain synthetic | Pending |

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

The assignment's `--host 0.0.0.0` command also works when needed. Set a nonempty
`DEMO_ACCESS_KEY` to require the `X-Demo-Key` header on analysis and both posting
routes. Enter it under Demo access in the UI. An empty key leaves these actions
open. Restart after configuration changes; do not remove the key to run tests.
Tests isolate application settings from the local key.

The analysis limiter permits two valid authorized attempts per client IP in a
rolling minute. Further attempts return 429 and Retry-After. Bad credentials and
invalid request bodies do not count. Automated tests use an isolated limiter.

## Read-only checks before publication

For Telegram setup and transport diagnosis, use:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_telegram
.\.venv\Scripts\python.exe -m scripts.check_telegram --transport
```

Both make read-only Telegram calls and hide tokens. The transport check now
prefers public IPv4 when available; this resolved the observed pinned-connection
timeout. It does not disable DNS validation, Host/SNI, or certificate checks.


1. Open `http://localhost:4000/docs` and check the request/response contracts.
2. Run `Invoke-RestMethod http://localhost:4000/health`; expect `status=ok`.
3. Send a request with a missing URL or a posting message without a CTA; expect
   HTTP 422 and no provider call when the correct demo key is supplied. Missing
   or incorrect keys return 401 first. Use the documented sample request shapes.
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
