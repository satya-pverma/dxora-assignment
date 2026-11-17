# Dxora Assignment

Python/FastAPI implementation of the two practical tests published in
[chivoxai/practical-test](https://github.com/chivoxai/practical-test).

## Status

The FastAPI foundation, website extraction service, `/link-analysis`, and
`/posting` orchestration are implemented, with Mastodon, Bluesky, and WordPress.com
publishing adapters. Tumblr and Telegram remain unimplemented. No live publishing
has been demonstrated; missing credentials produce explicit failures.

## Setup

Requires Python 3.11 or later.
Use a Python installation permitted by your machine's application policy.
On Windows, use the Python launcher to create the environment and invoke its
interpreter directly; activation is optional.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 4000
```

API documentation: http://localhost:4000/docs

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

## APIs

- `POST /link-analysis`: website extraction and structured LLM analysis.
- `POST /posting`: validated messages published through five independent integrations.
- `GET /health`: application health check.

## Posting API

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:4000/posting `
    -ContentType 'application/json' `
    -Body '{"message":"Discover our services https://example.com"}'
```

The message must contain at most 200 Unicode characters (including its link and
whitespace) and exactly one explicit HTTP(S) URL. URL credentials and invalid
control characters are rejected. Surrounding parentheses/angle brackets and
ordinary trailing punctuation are supported. The original message is preserved;
the separately extracted CTA is normalized for adapters. CTA validation does not
fetch the link or perform DNS resolution. URLs without `http://` or `https://`
are not accepted as the required CTA. Invalid request bodies return HTTP 422 and
are not sent to any adapter. Request fields other than `message` are forbidden.

Platform selection belongs to the server. `POSTING_PLATFORMS` is a nonempty JSON
array of unique names from `mastodon`, `bluesky`, `wordpress`, `tumblr`, and
`telegram`; the default selects all five. `POSTING_TIMEOUT_SECONDS` defaults to
15 and must be greater than zero and at most 60. Restart after changing `.env`.
With the example environment's empty credentials, Mastodon, Bluesky, and WordPress
return `Platform credentials are not configured on the server.` Tumblr and
Telegram return `This platform integration is not implemented yet.` Configuring
credentials enables real publication when `/posting` is called; starting the
server or running the tests does not publish messages.

See the [sample request](docs/examples/posting.request.json) and
[example default response](docs/examples/posting.response.json). These are
contract examples, not evidence of live publication.

For a valid request, HTTP 200 contains every selected platform's result, including
when all platforms fail. Each result has `platform`, `status`, `posted_url`,
`public_access`, `date`, `time`, and `error`. Overall `success` is true only if all
selected platforms confirm publication. Failed publications have null URL/date/
time and `public_access=false`. Dates and times are in UTC. A confirmed post whose
public access cannot be verified retains its success status, URL, and timestamp,
but has `public_access=false` and a verification explanation in `error`.

Adapters run concurrently with independent deadlines and results in configuration
order. Exceptions and timeouts do not stop the other platforms. Error messages are
sanitized rather than copied from upstream exceptions. Timeouts can occur after a
provider has published: verify the destination before retrying. No automatic
publication retry, durable idempotency, queue, or duplicate suppression is
implemented; sending the same valid request again may publish again.
`PlatformAdapter`/`PublishedPost` define the shared integration contract.

### First three platform adapters

Put credentials only in the ignored local `.env`, then restart the server.

| Adapter | Required configuration | Account prerequisites |
| --- | --- | --- |
| Mastodon | `MASTODON_BASE_URL`, `MASTODON_ACCESS_TOKEN` | Public HTTPS instance and a user token with `write:statuses` scope |
| Bluesky | `BLUESKY_PDS_URL`, `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` | Account, correct login/write PDS endpoint, and revocable app password |
| WordPress.com | `WORDPRESS_SITE_ID`, `WORDPRESS_ACCESS_TOKEN` | Owned public site and OAuth user token with publishing permission |

Mastodon and Bluesky base URLs must be HTTPS origins on port 443, with no paths,
credentials, query strings, or fragments. All outbound destinations are resolved
and pinned to public IPs, retaining Host/SNI and certificate validation. HTTP
redirects and environment proxies are disabled, and JSON responses are limited
to 256 KB. Tokens are sent only to the configured platform origin; WordPress
uses its fixed official API. Upstream errors are sanitized and writes are not
automatically retried, including after uncertain results.

Mastodon requests public visibility and verifies the created status ID, URL, and
content through an anonymous status read. WordPress escapes HTML, creates a
clickable CTA, requests `publish` status, and verifies ID/URL/content through an
anonymous API read. Bluesky creates a session, writes an `app.bsky.feed.post`
record with UTF-8 link facets, and checks its URI/text through the public AppView.
Its `createdAt` timestamp is generated locally in UTC and submitted with the
record. Configure the actual PDS for your account; the adapter does not discover
or follow response-provided service endpoints. It logs in once per invocation;
cross-request session caching and refresh are not implemented, so frequent calls
may hit login rate limits.

Anonymous verification has a separate three-second deadline after publication
confirmation. A platform can therefore take up to its publishing deadline plus
three seconds. Verification failure/timeout preserves the confirmed post URL and
returns `public_access=false`; Bluesky indexing delays or conservative text
matching may cause false negatives. A successful API publication alone is never
reported as proof of public access. Verification is a point-in-time API check,
not a guarantee of future visibility or indexing in search engines.

Adapter references: [Mastodon](https://docs.joinmastodon.org/methods/statuses/#create),
[Bluesky](https://docs.bsky.app/docs/tutorials/creating-a-post),
[WordPress.com](https://developer.wordpress.com/docs/api/1.1/post/sites/$site/posts/new/).

Posting milestone validation reported from the local Windows terminal with
Python 3.13.17: all 119 tests passed and Ruff reported all checks passed. The run
emitted one Starlette TestClient deprecation warning concerning HTTPX. Compilation,
OpenAPI generation, and local documentation links also passed checks in the editing
session. No live publishing was attempted during that milestone.
For the first-three-adapters milestone, local Windows verification with Python
3.13.17 passed all 150 tests and Ruff. The run emitted one Starlette TestClient
deprecation warning concerning HTTPX. Compilation, OpenAPI generation, and local
documentation links also passed checks in the editing session. All adapter tests
use simulated DNS/HTTP and fake credentials; live publishing and account access
remain unverified.

## Website analysis API

Set `OPENAI_API_KEY` in your ignored local `.env`. The server uses the OpenAI
Responses API with `LLM_MODEL=gpt-6-luna` by default. No key is required for
health checks or mocked tests. Restart the server after changing configuration.
Only the OpenAI adapter is implemented; alternative providers in the research
document are not automatic fallbacks.

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:4000/link-analysis `
    -ContentType 'application/json' -Body '{"url":"https://example.com"}'
```

See the [sample request](docs/examples/link-analysis.request.json) and
[complete synthetic response](docs/examples/link-analysis.response.json). The
response is a validated test fixture, not a real analysis of example.com.

The response includes `success`, `website`, `brand`, `analysis`, and `metadata`.
Analysis contains competitor comparisons, exactly five distinct search queries
covering Google/Facebook/Instagram/LinkedIn/X, SEO improvements, five service
entries, and target audiences. Metadata includes the source URL, model, provider
token usage when available, elapsed time, truncation, and evidence warnings.
Observed services require a source quote present in the extracted text. If the
page describes fewer than five services, additional ideas are explicitly marked
`inferred_recommendation`; these are not claims about existing offerings.
Competitors are always labelled `ai_suggestion` because independent competitor
research is not part of this adapter. SEO and audience insights are suggestions,
not measured rankings or search volumes. Quote matching checks textual presence;
it does not prove that every model interpretation is correct.

| HTTP status | Meaning |
| --- | --- |
| 200 | All five sections passed response validation |
| 400 | Destination blocked or redirect unsafe |
| 422 | Request body or URL format failed validation |
| 502 | Website/provider failure, malformed model output, refusal, incomplete output, or unsupported quote |
| 503 | Missing API key, provider authentication failure, or provider rate limit |
| 504 | Website or model deadline exceeded |

Service errors use `{"success":false,"error":{"code":"...","message":"..."}}`.
Request validation uses FastAPI's standard `detail` array. Upstream error bodies
and credentials are not returned to the caller.

`LLM_TIMEOUT_SECONDS` defaults to 30 (allowed range: greater than zero through
120). `LLM_MAX_OUTPUT_TOKENS` defaults to 6000 (allowed range: 1000–16000).
The website fetch has its separate 10-second deadline. The model receives the
cleaned page as untrusted data, with schema output and no tools. Provider requests
disable response storage (`store=false`), do not follow redirects, have a 256 KB
response bound, and are not retried automatically. This does not change the
provider's independent data-retention policies. Calls incur provider charges;
the 6000-token output cap is an upper bound, not measured usage or a cost estimate.
Caching, automatic fallback, and cross-model benchmarks remain future work.

Official contract: [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
Live model quality, actual token cost, and end-to-end latency have not been
benchmarked. Unit/integration tests simulate the provider and website responses.
Current milestone validation reported from the local Windows terminal with
Python 3.13.17: all 75 tests passed and Ruff reported all checks passed. Compilation
and OpenAPI generation also passed in the editing session. The test run emitted
one Starlette TestClient deprecation warning concerning HTTPX. Live provider and
HTTPS/SNI verification remain pending; the tests use simulated network responses.

See [the implementation plan](docs/PLAN.md) for milestones and acceptance criteria.
See [integration research](docs/INTEGRATION_RESEARCH.md) for the publishing APIs,
LLM comparison, recommended model, and account prerequisites.
All development branches and pull requests target this repository. No writes or
pull requests will be made to the assignment's source repository.

Never commit API keys, account tokens, or unsanitized demonstration logs.

## Website extraction service

`WebsiteExtractor` fetches one static HTML page and returns its requested/final
URL, title, description, headings, cleaned text, and truncation flag. It is an
internal service for the upcoming `/link-analysis` endpoint.

```python
import asyncio

from app.services.website_extractor import WebsiteExtractor

result = asyncio.run(WebsiteExtractor().extract("https://example.com"))
print(result.model_dump_json(indent=2))
```

Defaults: 10-second total fetch deadline, three redirects, 1 MB response limit,
and 24,000 extracted text characters. Constructor arguments can lower or raise
these limits. Only HTTP(S) on standard ports is accepted. Every destination must
resolve entirely to public IPs. Connections use a validated IP with the original
Host/SNI; proxies from environment variables and automatic redirects are disabled.
Credentials, nonpublic addresses, IPv6 transition addresses, and HTTPS downgrades
are rejected. TLS certificate validation remains enabled.

The service removes scripts, styles, navigation, footers, and explicit hidden
elements. It does not execute JavaScript, crawl linked pages, or interpret CSS
visibility. Compressed responses are deliberately rejected to bound memory usage;
the request asks for identity encoding. Sites that require JavaScript, compression,
or access challenges may fail with a structured `WebsiteError` (`code` and message).

Tests use simulated DNS and HTTP responses; they do not contact external websites:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_website_extractor.py
```

Validation reported from the local Windows environment with Python 3.13.17:
42 tests passed, and Ruff reported all checks passed. The run emitted one
Starlette TestClient deprecation warning concerning HTTPX. Live HTTPS/SNI
verification remains pending in an environment with outbound access.

## Manual GitHub workflow

The foundation is published on `main`. The remote is configured as
`https://github.com/satya-pverma/dxora-assignment.git`.

Each subsequent milestone uses a separate branch and pull request. Once the
working changes are on `feat/first-three-platforms`, review and publish them:

```powershell
git add .env.example README.md docs app tests/test_posting.py tests/test_platform_adapters.py
git commit -m "feat: integrate Mastodon Bluesky and WordPress publishing"
git push -u origin feat/first-three-platforms
```

Then open a pull request from `feat/first-three-platforms` into `main` in your own
repository. Review the changes and CI results before merging. Create the next
feature branch from the updated `main` after merging.
