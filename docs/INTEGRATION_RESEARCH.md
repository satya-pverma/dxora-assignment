# Integration research and implementation decisions

Research date: 17 November 2026. Scope: both practical tests. This document
records official API capabilities and proposed implementation choices. No live
publishing, account authentication, model benchmarking, or paid API calls were
performed. All five publishing integrations still need implementation and live
verification. Prices and account eligibility must be rechecked before deployment.

## Publishing platforms

Proposed primary set: Mastodon, Bluesky, WordPress.com, Tumblr, and Telegram
public channels. These provide text publishing without requiring media. The
Telegram channel is a public publication destination; a private chat is not
equivalent evidence. DEV/Forem is an alternative for developer-related messages.

| Platform | Publishing request and payload | Credentials and account access | Published URL and main constraints |
| --- | --- | --- | --- |
| Mastodon | `POST {instance}/api/v1/statuses`; `status=message`, `visibility=public` | Account on the chosen instance and user OAuth bearer token with `write:statuses` | Use the returned status URL. Check instance rules, account approval, character limits, and rate limits. |
| Bluesky | `POST {PDS}/xrpc/com.atproto.repo.createRecord`; collection `app.bsky.feed.post`, record containing `text`, `createdAt`, and a link facet | Bluesky account, handle and revocable app password for this local single-account tool; obtain/reuse a session and account DID | Convert returned record URI to `https://bsky.app/profile/{DID}/post/{rkey}`. Link facets use UTF-8 byte positions. Confirm the actual PDS and manage session expiry. |
| WordPress.com | `POST https://public-api.wordpress.com/rest/v1.1/sites/{site}/posts/new/`; escaped `content`, deterministic title, `status=publish` | Owned public site, OAuth application/token, and an author with publishing permission | Use response `URL`. Draft/private sites and insufficient publishing rights do not qualify as public publication. |
| Tumblr | `POST https://api.tumblr.com/v2/blog/{blog}/posts`; NPF text content block and `state=published` | Blog, registered application, user OAuth2 bearer token with `write`; `offline_access` if refresh is needed | Resolve the created post's public permalink using its ID. Use a public blog and manage token expiry. NPF is preferred over legacy posting. |
| Telegram | `POST https://api.telegram.org/bot{token}/sendMessage`; configured channel `chat_id` and plain `text` | Bot token and an owned public channel; bot needs channel administrator posting permission | `https://t.me/{channel_username}/{message_id}`. Requires a public username. Redact the bot token from request URLs and errors. |

Official sources:

- [Mastodon publishing, scopes and response](https://docs.joinmastodon.org/methods/statuses/#create).
- [Bluesky post creation](https://docs.bsky.app/docs/tutorials/creating-a-post),
  [posting guide](https://bsky.network/blog/create-post/), and
  [official account/app-password FAQ](https://bsky.social/about/blog/5-19-2023-user-faq).
- [WordPress.com create-post parameters and authentication](https://developer.wordpress.com/docs/api/1.1/post/sites/$site/posts/new/).
- [Tumblr OAuth2, NPF publishing, and rate limits](https://github.com/tumblr/docs/blob/master/api.md).
- [Telegram sendMessage and channel permissions](https://core.telegram.org/bots/api#sendmessage)
  and [public message links](https://core.telegram.org/api/links#public-message-links).

The reviewed publishing endpoint references do not specify a per-post dollar
charge for these ordinary text calls. That is not a guarantee of free accounts,
hosting, unlimited quotas, or approval. Confirm each account's access and terms;
honor rate limits and do not enable Telegram paid broadcasting for this test.

### Alternative: DEV/Forem

[The official API](https://developers.forem.com/api/v0#tag/articles/operation/createArticle)
supports `POST https://dev.to/api/articles`, an `api-key` header, User-Agent, and
an `article` object with title, body_markdown, and `published=true`. It returns
the article URL. Creation is limited to 10 requests per 30 seconds in the reviewed
reference. Use only when the message is appropriate for a developer community;
do not use it as a generic advertising destination. Access is not yet verified.

### Posting service decisions

These are implementation proposals, not claims about completed functionality:

- Select destinations from server configuration; the request contains only
  `message`. Return a result for each selected platform even when credentials
  are missing. Missing credentials are failures, never simulated successes.
- Validate the complete message as at most 200 Python Unicode characters with
  exactly one HTTP(S) CTA URL. Preserve the message in platform-specific text
  encodings; escape HTML where necessary and avoid Markdown interpretation.
- Use independent bounded async calls and per-platform timeouts. One platform's
  exception must not cancel the others. Handle 401/403, 429, network failure,
  malformed responses, and provider errors independently.
- Avoid blind retries of publishing POSTs: an interrupted response may follow a
  successful publication. Use provider-supported idempotency where available;
  otherwise return an explicit uncertain-outcome error and require reconciliation.
- A returned URL does not prove public access. Verify the intended post without
  credentials using a bounded fetch and content/identifier checks. Report false
  with a verification explanation if blocked or inconclusive; this is not proof
  the post is private. Preserve the successful publication result and URL.
- Record provider timestamps where available, otherwise local completion time,
  using UTC for API date/time fields and documenting that convention. Overall
  `success` means every selected platform published; inspect individual results
  for partial success.

## LLM comparison

Standard synchronous text rates in USD per million tokens, excluding caching,
batch discounts, search/tools, taxes, and retries. The example uses 8,000 total
input tokens and 2,000 billable output tokens. These are planning assumptions,
not measured usage; reasoning tokens can increase the output bill.

| Provider / model ID | Input / output rate | Context capacity | Structured output | Example cost | Speed and accuracy assessment |
| --- | --- | --- | --- | --- | --- |
| OpenAI `gpt-6-luna` | $0.10 / $0.50 | 1,050,000 tokens | Supported | $0.0018 | Proposed low-cost baseline; no application latency or accuracy measurements yet. |
| Google `gemini-3.8-flash` | $0.75 / $3.75 through 31 Dec 2026; $1.50 / $7.50 from 1 Jan 2027 | 1,048,576 input tokens | Supported | $0.0135 at current promotional rate | Candidate for richer analysis; quality and speed relative to alternatives are unmeasured. |
| Anthropic `claude-haiku-5-5` | $0.10 / $0.50 for prompts up to 100,000 tokens; $0.50 / $2.50 above that threshold | 1M tokens | JSON schema output supported by Claude structured-output API; verify selected model/account in integration tests | $0.0018 in the lower prompt tier | Provider describes it as latency-sensitive; no application benchmark confirms superiority. |

Sources checked:

- [OpenAI pricing](https://developers.openai.com/api/docs/pricing),
  [GPT-6 Luna capabilities and limits](https://developers.openai.com/api/docs/models/gpt-6-luna).
- [Google pricing](https://aistudio.google.com/docs/pricing#gemini-3.8-flash),
  [Gemini 3.8 Flash capabilities and limits](https://aistudio.google.com/docs/models/gemini-3.8-flash).
- [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing),
  [Haiku 5.5 limits](https://platform.claude.com/docs/en/models/haiku-5-5/overview),
  [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).

Cost formula: `(input_tokens * input_rate + output_tokens * output_rate) / 1,000,000`.
For example, Luna: `(8000 * 0.10 + 2000 * 0.50) / 1,000,000 = $0.0018`.
Use each provider's actual usage counters because tokenizers differ.

### Recommendation and fallback

Start with OpenAI `gpt-6-luna` through the Responses API, configured by environment
variables. The decision is provisional: low listed cost, schema output support,
and ample context fit a bounded extraction task. No model has demonstrated
maximum accuracy on this assignment. Use low/no reasoning where supported and
retain Pydantic validation of every returned section.

Use `gemini-3.8-flash` as an explicitly configured alternative if the baseline
fails the quality evaluation or is unavailable. Haiku 5.5 is a competing economical
option worth benchmarking. Implement one provider first; a comparison does not
require three production adapters. Automatic cross-provider fallback is deferred
until both adapters pass contract tests and its extra cost is documented.

Estimated response-time budget: 5–20 seconds for one model request and up to
10 seconds for website extraction, targeting an ordinary end-to-end response
within 30 seconds. These are engineering targets, not provider SLAs or measured
latency; overloaded providers and difficult sites can exceed them. Enforce explicit
timeouts and return useful errors rather than promising the target.

### Quality, evidence, and cost controls

Proposed extraction/prompt budget: approximately 6,000 tokens of cleaned content
plus 2,000 tokens of instructions, schema, and metadata. Start with a homepage;
add bounded same-site service/about pages only if evidence is insufficient. Do
not send raw HTML, scripts, duplicate navigation, credentials, or arbitrary files.
Cap response size and total billable output, allowing for provider-specific
reasoning accounting. Treat truncation, refusal, and schema mismatch as errors.

Website text is untrusted input, including embedded instructions. The model must
use it as evidence, not as authority to change its task or invoke tools. Keep
source URLs and extracted evidence separate from instructions. Competitors
without independent evidence must be marked as suggestions; lack of five real
services must not lead to five fabricated offerings. Inferred recommendations
must be distinguishable from observed services. Do not invent search volumes.

Use one structured request for all five sections. Cache successful analysis by
normalized URL, extracted-content hash, provider/model, prompt/schema version,
and a bounded TTL. Cache failures separately only if deliberately designed.
Do not enable paid search grounding implicitly. Search-based competitor research
requires explicit sources and separate cost accounting.

Benchmark during the analysis milestone using the same saved public-site fixtures
and rubric for each accessible candidate. Include a service business, product
business, sparse page, non-English page, and adversarial embedded instructions.
Record sample size, model/version, reasoning settings, input/output usage,
schema pass rate, unsupported-claim count, field coverage, reviewer scores,
median/p95 latency, and total cost. Use repeated runs and retain sanitized output.
Until then, every performance and accuracy claim remains unmeasured.

## Account prerequisites before live testing

Store secrets in the ignored local `.env`, never in commits, PRs, screenshots,
chat messages, or logs. The OpenAI adapter now reads `OPENAI_API_KEY`, `LLM_MODEL`,
`LLM_TIMEOUT_SECONDS`, and `LLM_MAX_OUTPUT_TOKENS`. Other integration variable
names below remain proposals and are not read by the application yet.

| Integration | Proposed configuration | Readiness |
| --- | --- | --- |
| OpenAI | `OPENAI_API_KEY`, `LLM_MODEL=gpt-6-luna` | Account, model entitlement, and API billing unverified |
| Gemini alternative | `GEMINI_API_KEY`, alternative model ID | Account and quota unverified |
| Mastodon | `MASTODON_BASE_URL`, `MASTODON_ACCESS_TOKEN` | Account and token unverified |
| Bluesky | `BLUESKY_PDS_URL`, `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` | Account and session flow unverified |
| WordPress.com | `WORDPRESS_SITE_ID`, `WORDPRESS_ACCESS_TOKEN` | Public site and publishing rights unverified |
| Tumblr | `TUMBLR_BLOG_IDENTIFIER`, `TUMBLR_ACCESS_TOKEN`; OAuth client/refresh secrets if refreshing | Blog and OAuth registration unverified |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, `TELEGRAM_CHANNEL_USERNAME` | Public channel and bot posting rights unverified |

Before recording the final demonstration, verify all five destinations with
working credentials and an authorized test message. If access fails, document
the failure and select a suitable researched replacement; do not silently count
an unimplemented adapter, private chat, or mock response as successful publication.
