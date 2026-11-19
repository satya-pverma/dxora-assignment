# Tumblr automatic token refresh

Install `requirements.txt`. Set these privately in local `.env` and Render Environment:

```dotenv
TUMBLR_AUTO_REFRESH=true
TUMBLR_CLIENT_ID=your_oauth_consumer_key
TUMBLR_CLIENT_SECRET=your_oauth_consumer_secret
TUMBLR_BLOG_IDENTIFIER=your-blog.tumblr.com
TUMBLR_ACCESS_TOKEN=initial_access_token
TUMBLR_REFRESH_TOKEN=latest_refresh_token
MONGODB_URI=mongodb+srv://...
MONGODB_DATABASE=dxora_assignment
MONGODB_COLLECTION=tokens
TOKEN_ENCRYPTION_KEY=your_fernet_key
POSTING_TIMEOUT_SECONDS=30
```

Generate the encryption key once, copying it directly to the clipboard:

```powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" | Set-Clipboard
```

Paste it into `TOKEN_ENCRYPTION_KEY`. Retain the same key across deployments;
changing it makes stored tokens unreadable. Use an Atlas database user with
readWrite limited to `dxora_assignment`. Allow your computer and Render outbound
addresses in Atlas Network Access. Secrets must remain out of Git and screenshots.

Authorize Tumblr with `basic write offline_access`. The bootstrap refresh token
and Consumer Key/Secret must belong to the same app. MongoDB stores encrypted
tokens in the configured collection (`tokens` by default), keyed by app ID and blog hostname.

## Initialize

This optional command initializes a missing record without calling Tumblr or posting:

```powershell
.\.venv\Scripts\python.exe -m scripts.init_tumblr_tokens
```

The first publishing request can initialize a missing record too. Because the
initial issuance time is unknown, it refreshes before the first publication.
Later requests refresh within 90 seconds of expiry. No scheduled job is needed.
Both replacement tokens are persisted with majority acknowledgement before posting.
Existing records take precedence over stale `.env` values after redeployment.
Bootstrap access/refresh environment tokens can be removed after successful seeding;
retain client credentials, MongoDB settings and the encryption key.

Restart locally and test with Tumblr only selected. Deploy code and settings to
Render. Test renewal by posting after expiry and confirming the stored version and
expiry advance. The credential-presence check does not contact MongoDB or validate tokens.

Local and Render sharing one database/app/blog record MUST use the same encryption
key. For isolation use separate OAuth apps/databases; do not seed one rotating
refresh token into independent stores.

## Failure and recovery

Without Render Shell, use Swagger `/docs` to execute the demo-key-protected
`GET /dashboard/diagnostics/tumblr` endpoint. Enter the `x-demo-key` header.
It performs credential-free GETs to the fixed OAuth endpoint using hostname and
public IPv4 over HTTP/1.1, plus hostname with HTTP/2 negotiation, preserving Host/SNI
and certificate validation. Any HTTP response
proves HTTPS connectivity, not successful token refresh. The response includes
only status, timing and safe failure stage/type. Checks are limited to two per
minute per process; no database changes, OAuth renewal or publication occur.
It also sends one empty form POST to the token endpoint and an unauthenticated GET
to `/v2/user/info` to distinguish token-path/method failures from general API access.
No request contains a valid OAuth grant, credentials or refresh token. A protocol
error includes an allowlisted reason, never the raw upstream exception message.
DNS resolution runs in the worker thread and follows system resolver timeouts;
each HTTP probe has an eight-second timeout.
If `hostname_http2` succeeds with `http_version=HTTP/2` while HTTP/1.1 probes fail,
set `TUMBLR_REFRESH_HTTP2=true` in Render and redeploy to use it for renewal.
HTTP/2 is optional and disabled for renewal by default until verified. Enabling it
allows protocol negotiation; a server without HTTP/2 support can still select HTTP/1.1.
Do not switch protocols as an automatic retry of an uncertain OAuth POST.

Run a read-only connection and decryption diagnostic in the environment that fails:

```powershell
.\.venv\Scripts\python.exe -m scripts.check_tumblr_storage
```

On a host with Python on PATH, use `python -m scripts.check_tumblr_storage`.
It does not seed, refresh, publish or print secrets. A successful local check does
not prove Render is allowed by Atlas Network Access. Use the same encryption key,
database, collection and app/blog identity wherever sharing one record.
New refresh failures retain an allowlisted `last_error` category in the record;
the diagnostic shows it without exposing token values or upstream error descriptions.
Older failed records have no saved reason. Initialization/decryption checks do not
test OAuth client credentials, and initialization deliberately forces first-use refresh.

An atomic compare-and-set claim prevents concurrent workers refreshing the same
token. Other requests wait briefly or return a busy error. Database/encryption
errors fail closed rather than reverting to old environment tokens. Static-token
behavior remains available when `TUMBLR_AUTO_REFRESH=false`.

OAuth rotation and MongoDB persistence cannot be one atomic transaction. A crash,
timeout, invalid refresh response or failed save can leave rotation uncertain.
Connection-establishment failures before sending OAuth leave the record ready for
a later request; read/write failures remain uncertain. Safe Render logs show only
the connection stage and exception class, without trace details or credentials.
The code never replays an uncertain refresh or steals an abandoned claim. A claim
older than 60 seconds requires reauthorization. Obtain fresh tokens, update `.env`,
stop posting in ALL environments sharing this record, then explicitly replace it:

```powershell
.\.venv\Scripts\python.exe -m scripts.init_tumblr_tokens --replace
```

This replaces only the identified app/blog record. Resume publishing after success.
No publication is retried automatically. A cancelled publication may leave a token
worker finishing its save in the background; that worker never publishes anything.
If the overall publication times out, check the blog before retrying.

Automated tests use fake storage/HTTP, not live Atlas. Renewal still requires an
end-to-end check with your configured Atlas database and Tumblr credentials.
