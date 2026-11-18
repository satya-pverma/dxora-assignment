# Dxora Assignment

Python/FastAPI implementation of the two practical tests published in
[chivoxai/practical-test](https://github.com/chivoxai/practical-test).

## Status

Status reviewed on **18 November 2026** against both source assignment documents.
Website extraction, Gemini-powered analysis, and all five publishing adapters are
implemented. The developer's latest full Windows/Python 3.13.17 run reports
**255 tests passed and Ruff passed**. Tests use fake providers and do not publish.

The live analysis uses **Google Gemini `gemini-3.1-flash-lite`** on the developer's
free-tier project. Four-platform publication succeeded in one live request:

| Platform | Publication | Automatic public-access verification |
| --- | --- | --- |
| Mastodon | Confirmed | Inconclusive; anonymous manual check pending |
| Bluesky | Confirmed | Passed |
| Tumblr | Confirmed | Inconclusive; anonymous manual check pending |
| Telegram | Confirmed | Passed |
| WordPress.com | Adapter implemented; live test deferred | Pending |

Public deployment and its live `/docs` URL remain pending. A Render configuration
is supplied, not evidence of deployment. The [live four-platform response](docs/evidence/posting-live-2026-11-18.json) is
recorded; analysis and deployment evidence still need to be archived. See the [verification record](docs/VERIFICATION.md),
[submission checklist](docs/SUBMISSION_CHECKLIST.md),
[implementation plan](docs/PLAN.md), and [deployment guide](docs/DEPLOYMENT.md).

## Setup

Requires Python 3.11 or later.
Use a Python installation permitted by your machine's application policy.
On Windows, use the Python launcher to create the environment and invoke its
interpreter directly; activation is optional.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-tested.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 4000
```

`requirements-tested.txt` snapshots the tested Windows/Python 3.13 package
versions, including test tools. For other supported environments, install
`requirements-dev.txt` instead; it uses version ranges. This repository's CI
checks Linux/Python 3.11 with those ranges and Windows/Python 3.13 with the
snapshot. CI results must be checked on the actual PR. The assignment's server
command may use `--host 0.0.0.0` on the same port; the local default above binds
only to your machine. Set `DEMO_ACCESS_KEY` to protect analysis and publishing.
Requests then require `X-Demo-Key`; the UI sends the entered demo key. An empty
setting leaves those actions open. Health, the UI, and documentation remain public.

Browser UI: http://localhost:4000 | API documentation: http://localhost:4000/docs

Configure the working analysis provider in `.env` (never commit actual secrets):

```dotenv
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_API_KEY=your_private_key
LLM_TIMEOUT_SECONDS=90
LLM_MAX_OUTPUT_TOKENS=6000
DEMO_ACCESS_KEY=your_private_demo_password
```

The environment template selects Gemini. The Python Settings fallback remains
OpenAI when `LLM_PROVIDER` is omitted; use the explicit configuration above.
Restart the server after changing environment values. The UI never receives
provider credentials.

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.check_credentials
```

## APIs

- `POST /link-analysis`: website extraction and structured LLM analysis.
- `POST /posting`: validated messages published through five independent integrations.
- `GET /health`: application health check.
- `GET /`: browser workspace for analysis and publishing.
- `GET /dashboard/platforms`: names and configuration availability, never secrets.
- `POST /dashboard/posting`: UI-only message plus a validated platform selection.

The assignment's `/posting` endpoint still accepts only `message` and chooses its
platforms internally. The optional dashboard endpoint adds user selection without
changing that contract. The UI requires a selection and publication confirmation.

## Posting API

```powershell
$demoKey = Read-Host 'Demo access key' -AsSecureString
$headers = @{ 'X-Demo-Key' = [System.Net.NetworkCredential]::new('', $demoKey).Password }
Invoke-RestMethod -Method Post -Uri http://localhost:4000/posting `
    -Headers $headers `
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
With the example environment's empty credentials, all five platforms return
`Platform credentials are not configured on the server.` Configuring
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

### Tumblr and Telegram adapters

| Adapter | Required configuration | Prerequisites |
| --- | --- | --- |
| Tumblr | `TUMBLR_BLOG_IDENTIFIER`, `TUMBLR_ACCESS_TOKEN` | Public Tumblr blog and current OAuth2 user token with `write` scope |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_USERNAME` | Public channel and a bot with administrator posting permission |

Tumblr accepts a blog name or `name.tumblr.com`, publishes an NPF text block with
explicit CTA formatting, and checks its canonical permalink and message without
authentication. Formatting offsets count Unicode code points. The returned ID
must be a positive unsigned 64-bit decimal string. Its response lacks a publication
timestamp, so the adapter records local UTC completion time. Custom blog domains
and UUID identifiers are not supported by this implementation. Obtain OAuth tokens
outside this application and renew them manually; token acquisition/refresh is not
implemented. Redirects, login challenges, larger themes, compression, or missing
canonical markup can cause a public page to remain unverified.

Telegram accepts a public channel username with or without `@`. Optionally set
`TELEGRAM_CHANNEL_ID` to the channel's `-100...` numeric ID. Before sending, it
calls `getChat` and requires the expected channel type, public username, and
configured ID (if supplied). It sends plain text once, without Markdown/HTML
interpretation or paid broadcasting. The response must identify the same channel,
message text, positive message ID, and a valid Unix timestamp. An anonymous `t.me`
embed check verifies the exact channel/message widget and text. Private chats and
groups are rejected by the preflight. No permissions are granted by the application.

Telegram requires its bot token in the transport path. The application inserts
that path beneath HTTPX's normal request logging, which sees only `botredacted`;
transport errors are sanitized. Do not enable external wire/body tracing or record
credentials in screenshots. The visibility check carries no bot token. The shared
public-address pinning, response bounds, no-redirect policy, and separate visibility
deadline also apply to both adapters.

References: [Tumblr API](https://github.com/tumblr/docs/blob/master/api.md),
[NPF formatting](https://github.com/tumblr/docs/blob/master/npf-spec.md),
[Telegram Bot API](https://core.telegram.org/bots/api#sendmessage),
[public message links](https://core.telegram.org/api/links#public-message-links).

Tests cover all five adapters, partial failures, visibility checks, bounded HTTP,
configuration validation, and token-safe logging using simulated DNS/HTTP and
fake credentials. Live publication results are recorded separately above. See [recorded verification](docs/VERIFICATION.md) for the results and
the remaining live checks.

## Browser workspace and hosting

Open `/` for section-based analysis reports and publishing controls. The six
report tabs cover overview, competitors, search queries, SEO, services, and
audience. Full JSON remains expandable. Platform checkboxes show availability
from server settings; only enabled platforms with credential fields can be
selected. This presence check is not proof of account permissions.

For the four tested destinations, set:

```dotenv
POSTING_PLATFORMS=["mastodon","bluesky","tumblr","telegram"]
```

Enable `wordpress` once its owned site/token are ready for testing. `/posting`
publishes to all server-selected platforms; the dashboard publishes only to its
selected subset. Neither flow automatically retries a publication.

See [free Render deployment](docs/DEPLOYMENT.md). Set the demo access key and
provider secrets in the hosting dashboard; never upload `.env`. Public deployment
is required by the latest link-analysis assignment and is not completed yet.

## Website analysis API

Select a provider in your ignored local `.env`. For Gemini, set
`LLM_PROVIDER=gemini`, `GEMINI_API_KEY` and `GEMINI_MODEL=gemini-3.1-flash-lite`.
For the optional OpenAI adapter, set `LLM_PROVIDER=openai`, `OPENAI_API_KEY` and
`LLM_MODEL=gpt-6-luna`. Both adapters use the same validated analysis contract.
Restart the server after changing configuration. No key is required for health
checks or mocked tests. There is no automatic provider fallback.

Run `python -m scripts.list_gemini_models` to list model IDs available to your key
without generating content. Model availability does not guarantee free quota;
check your project's AI Studio Rate Limit page before testing. Gemini free tier
requests may be used to improve Google products; use public website content.

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:4000/link-analysis `
    -Headers $headers `
    -ContentType 'application/json' -Body '{"url":"https://example.com"}'
```

See the [sample request](docs/examples/link-analysis.request.json) and
[complete synthetic response](docs/examples/link-analysis.response.json). The
response is a validated test fixture, not a real analysis of example.com.
The PowerShell example reuses `$headers` from the posting example; supply your
demo key whenever `DEMO_ACCESS_KEY` is set.

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
| 401 | Missing or incorrect demo access key |
| 429 | Two analysis attempts per client IP in 60 seconds exceeded; inspect Retry-After |
| 400 | Destination blocked or redirect unsafe |
| 422 | Request body or URL format failed validation |
| 502 | Website/provider failure, malformed model output, refusal, incomplete output, or unsupported quote |
| 503 | Missing API key, provider authentication failure, or provider rate limit |
| 504 | Website or model deadline exceeded |

Service errors use `{"success":false,"error":{"code":"...","message":"..."}}`.
Request validation uses FastAPI's standard `detail` array. Upstream error bodies
and credentials are not returned to the caller.

OpenAI HTTP 429 responses are classified using bounded, allowlisted error codes.
`llm_quota_exceeded` means API quota/credits or usage limits need checking;
`llm_credit_balance_exhausted` identifies exhausted prepaid credits. Separate codes
identify project/organization spend limits and organization usage limits.
`llm_rate_limited` covers transient or unclassified limits. Do not repeatedly
retry a billing/quota error; inspect the API organization's billing and limits.
These errors retain HTTP 503 and never expose the provider's raw account message.

`LLM_TIMEOUT_SECONDS` has a code fallback of 30 seconds; the supplied template
and current demo use 90 seconds (allowed range: greater than zero through 120). `LLM_MAX_OUTPUT_TOKENS` defaults to 6000 (allowed range: 1000–16000).
The website fetch has its separate 10-second deadline. The model receives the
cleaned page as untrusted data, with schema output and no tools. Both provider requests disable proxies and redirects, have a 256 KB response
bound, and are not retried automatically. OpenAI additionally sets `store=false`. This does not change the
provider's independent data-retention policies. Paid-tier calls incur provider charges; eligible Gemini free-tier calls use project quota;
the 6000-token output cap is an upper bound, not measured usage or a cost estimate.
Caching, automatic fallback, and cross-model benchmarks remain future work.

Official contract: [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
Live Gemini responses were reviewed locally. One observed response reported
14.073 seconds end to end; this single observation is not a speed benchmark or
accuracy score. Actual token usage and account billing have not been archived.
Unit/integration tests simulate provider and website responses.

Analysis is limited to two valid, authorized attempts per client IP in a rolling
60-second window. A rejected request returns HTTP 429 with `Retry-After`; the UI
displays the wait time. Provider failures still count. The in-memory limit resets
on restart and assumes one worker/instance. See the deployment guide for proxy
and shared-storage limitations. Publishing is unaffected by this analysis limit.

## LLM comparison and selection

**Selected provider/model: Google Gemini `gemini-3.1-flash-lite`.** It generated
schema-valid analysis in the developer's live tests using available free quota.
This practical choice avoids buying credits for the demo and supports the shared
JSON contract. It is not a claim that this model is the most accurate or fastest.

The assignment asks for research on at least three models/providers, not three
active integrations. OpenAI is an implemented, explicitly configured alternative;
its local live test was blocked by exhausted API credits. Anthropic is researched
but has no adapter. Automatic provider fallback is not implemented.

| Candidate | Standard text input / output per million tokens | Input context | Schema output | Estimated cost: 8k input + 2k billable output |
| --- | --- | --- | --- | --- |
| Gemini `gemini-3.1-flash-lite` (selected) | Free within eligible quota; paid $0.25 / $1.50 | 1,048,576 | Supported; live analysis passed | Free within quota; $0.005 paid-tier estimate |
| OpenAI `gpt-6-luna` | $0.10 / $0.50 | 1,050,000 | Supported; mocked adapter tests | $0.0018 estimate |
| Anthropic `claude-haiku-5-5` | $0.10 / $0.50 through 100k prompt tokens | 1M | Supported; not integrated | $0.0018 estimate |

Google rates and model limits were checked on 18 November 2026; the other two
rows retain the dated 17 November research. Verify availability and current
prices before switching. These costs exclude tools, retries, taxes and caching;
billable output includes reasoning. The selected model's 6,000-output-token cap
is a limit, not measured usage. Free quota is account-specific and not an SLA;
Google may use free-tier requests to improve products. Use public website content.

[Google pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.1-flash-lite)
and [model limits](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite).
Planning input/output budget: 8,000/2,000 tokens; paid estimate:
`(8000 * 0.25 + 2000 * 1.50) / 1000000 = $0.005`.

Observed local latency is roughly 14 seconds for one recorded run, including
extraction. Performance across sites/models and factual accuracy remain
unbenchmarked. Gemini uses low thinking for Gemini 3 models and local Pydantic
validation. Content cleaning, truncation and a single call for all five sections
reduce token use. Caching, automatic fallback and token refresh are future work.

[The detailed research report](docs/INTEGRATION_RESEARCH.md) includes official
pricing/model sources, cost calculations, caveats, a benchmark rubric, and the
fallback recommendation. Recheck prices and model entitlement before live use.

See [the implementation plan](docs/PLAN.md) for milestones and acceptance criteria.
See [integration research](docs/INTEGRATION_RESEARCH.md) for the publishing APIs,
LLM comparison, recommended model, and account prerequisites.
All development branches and pull requests target this repository. No writes or
pull requests will be made to the assignment's source repository.

Never commit API keys, account tokens, or unsanitized demonstration logs.

## Website extraction service

`WebsiteExtractor` fetches one static HTML page and returns its requested/final
URL, title, description, headings, cleaned text, and truncation flag. It is an
internal service used by the `/link-analysis` endpoint.

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

Live HTTPS/SNI verification remains pending. The full mocked regression result
and known TestClient deprecation warning are recorded in the verification report.

## Manual GitHub workflow

Use a new feature branch from updated `main`, commit the reviewed changes, and
open a PR into this repository's `main`. Check the actual PR CI before merging.
The assignment source repository is read-only for this project. The developer
handles GitHub commits, pushes, PRs and merges manually.

## Assignment submission

| Source document | Deadline | Required email subject |
| --- | --- | --- |
| [Link analysis](https://github.com/chivoxai/practical-test/blob/main/link-analysis.md) | 27 November 2026 (source typo: "27nd") | Your Name - Python Practical Link Analysis test review |
| [Posting](https://github.com/chivoxai/practical-test/blob/main/python-post-message.md) | 22 November 2026 | Your Name - Python Practical test review |

The analysis submission requires a public working demo URL and `/docs`, plus the
public repository, setup instructions, examples, LLM comparison, final model
recommendation and sanitized evidence. Both documents require applicant details
and the specified LinkedIn/Instagram follows and profile links. Those personal
steps and the submission emails have not been verified or performed by this app.
Use the [submission checklist](docs/SUBMISSION_CHECKLIST.md) for outstanding work.
