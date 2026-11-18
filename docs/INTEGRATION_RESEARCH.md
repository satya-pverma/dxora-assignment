# Integration research and implementation decisions

Initial research: 17 November 2026; status and Gemini selection updated on
**18 November 2026**. Five publishing adapters are implemented. A live combined
request confirmed Mastodon, Bluesky, Tumblr and Telegram publication; automated
public-access verification passed for Bluesky/Telegram and was inconclusive for
Mastodon/Tumblr. WordPress live testing is deferred. Gemini 3.1 Flash-Lite now
powers the working analysis; OpenAI remains an optional implemented adapter.
This is integration evidence, not a comparative model benchmark. See
[the verification record](VERIFICATION.md) for what remains unverified.

## Publishing platforms

Implemented set: Mastodon, Bluesky, WordPress.com, Tumblr, and Telegram
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
| OpenAI `gpt-6-luna` | $0.10 / $0.50 | 1,050,000 tokens | Supported | $0.0018 | Implemented manual alternative; live generation blocked by exhausted account credits. |
| Google `gemini-3.1-flash-lite` (selected) | Free within eligible project quota; paid text $0.25 / $1.50 | 1,048,576 input tokens | Supported; live analysis validated | $0 within free quota; $0.005 paid estimate | One observed end-to-end response: 14.073s; cross-model accuracy and latency unbenchmarked. |
| Anthropic `claude-haiku-5-5` | $0.10 / $0.50 for prompts up to 100,000 tokens; $0.50 / $2.50 above that threshold | 1M tokens | JSON schema output supported by Claude structured-output API; verify selected model/account in integration tests | $0.0018 in the lower prompt tier | Provider describes it as latency-sensitive; no application benchmark confirms superiority. |

Sources: Gemini pricing/model limits rechecked 18 November 2026; other candidate rates retain the 17 November research date. Recheck before switching providers.

- [OpenAI pricing](https://developers.openai.com/api/docs/pricing),
  [GPT-6 Luna capabilities and limits](https://developers.openai.com/api/docs/models/gpt-6-luna).
- [Google pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.1-flash-lite),
  [Gemini 3.1 Flash-Lite capabilities and limits](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite).
- [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing),
  [Haiku 5.5 limits](https://platform.claude.com/docs/en/models/haiku-5-5/overview),
  [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).

Cost formula: `(input_tokens * input_rate + output_tokens * output_rate) / 1,000,000`.
For example, Luna: `(8000 * 0.10 + 2000 * 0.50) / 1,000,000 = $0.0018`.
Use each provider's actual usage counters because tokenizers differ.

### Recommendation and fallback

Use **Google Gemini `gemini-3.1-flash-lite`** for the current assignment demo.
It produced the required structured response with the developer's free-tier key;
its supported JSON schema output, low paid-tier text cost and adequate context
fit the bounded website input. This recommendation prioritizes the demonstrated
account access and schema-valid output, not an untested claim of best accuracy.

Configuration: `LLM_PROVIDER=gemini`, `GEMINI_MODEL=gemini-3.1-flash-lite`,
`GEMINI_API_KEY`, `LLM_TIMEOUT_SECONDS=90`, `LLM_MAX_OUTPUT_TOKENS=6000`.
The Gemini 3 adapter requests low thinking and uses Pydantic validation. Expected
input/output for cost planning remains 8,000/2,000 tokens, not observed usage.
At paid text rates, `(8000 * 0.25 + 2000 * 1.50) / 1000000 = $0.005` per analysis;
eligible free-tier text is $0 within quota. Include billable thinking output in
real accounting. Free quotas, availability, and data-use policies are project-
and tier-specific. Only public website content is used in the demo.

One observed response took 14.073s including extraction. This is a single local
observation, not median/p95 latency, an SLA, or a quality benchmark. Model calls
have the configured 90s timeout for the demo and a separate 10s website deadline.
Provider load, network and output length affect the observed time.

OpenAI `gpt-6-luna` is the implemented, manually configurable alternative once
billing/model access are available. The live account test reached an exhausted
credit balance; successful generation remains unverified. Anthropic is research-
only. Compare these candidates using the rubric below before making quality
claims. Three production adapters are not required by the research section.
Automatic fallback is not implemented and cannot silently incur another charge.

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
and a bounded TTL. Cache failures separately only if deliberately designed. Caching in this paragraph
is a proposed optimization; the application does not currently cache results.
Do not enable paid search grounding implicitly. Search-based competitor research
requires explicit sources and separate cost accounting.

For a future comparative benchmark, use the same saved public-site fixtures
and rubric for each accessible candidate. Include a service business, product
business, sparse page, non-English page, and adversarial embedded instructions.
Record sample size, model/version, reasoning settings, input/output usage,
schema pass rate, unsupported-claim count, field coverage, reviewer scores,
median/p95 latency, and total cost. Use repeated runs and retain sanitized output.
Until then, relative performance and accuracy remain unmeasured; the single
observed Gemini latency above does not establish superiority.

## Account prerequisites before live testing

Store secrets in the ignored local `.env`, never in source, PRs, screenshots,
chat, or logs. The selected Gemini configuration is documented above. The optional
OpenAI adapter uses `OPENAI_API_KEY` and `LLM_MODEL`. Both share timeout/output
limits. The publishing adapters use `POSTING_PLATFORMS` and platform credentials.
Changing these values requires a server restart. Token refresh is manual.

| Integration | Configuration | Verified status |
| --- | --- | --- |
| Gemini | `LLM_PROVIDER=gemini`, `GEMINI_MODEL=gemini-3.1-flash-lite`, `GEMINI_API_KEY` | Live structured analysis passed |
| OpenAI | `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, `LLM_MODEL` | Adapter tested with mocks; account credit exhausted |
| Mastodon | `MASTODON_BASE_URL`, `MASTODON_ACCESS_TOKEN` | Published; automatic public check inconclusive |
| Bluesky | `BLUESKY_PDS_URL`, `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` | Published and public check passed |
| WordPress.com | `WORDPRESS_SITE_ID`, `WORDPRESS_ACCESS_TOKEN` | Implemented; live setup/test deferred |
| Tumblr | `TUMBLR_BLOG_IDENTIFIER`, `TUMBLR_ACCESS_TOKEN` | OAuth2 authorized and published; public check inconclusive |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_USERNAME`; optional `TELEGRAM_CHANNEL_ID` | Bot permissions, transport, publication and public check passed |

For final evidence, finish the fifth destination and check anonymous post links.
Do not count mock fixtures as publication or an inconclusive public check as proof
that a post is private. Reconcile uncertain outcomes before retrying writes.
