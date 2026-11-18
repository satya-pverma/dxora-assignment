# UI and free deployment

The same FastAPI service serves the browser UI at `/`, Swagger at `/docs`, and
both JSON endpoints. There is no frontend build, second service, database, or
browser-side provider key. Analysis and publishing run independently.

`/link-analysis` allows two requests per client IP in a rolling 60-second window.
Further requests return HTTP 429 and `Retry-After` seconds; the UI displays the
wait time. Valid authorized attempts count even if a provider later fails.
Invalid request bodies and rejected demo keys do not consume the analysis limit.
Publishing and health checks are unaffected. Clients sharing an IP share a quota.

The limiter is in memory: restart resets it. Run a single Uvicorn worker/instance
with the supplied start command. Multiple workers/replicas require shared storage
such as Redis for a consistent limit. The app uses the ASGI connection IP, not
arbitrary forwarded headers. Behind a proxy, configure Uvicorn's trusted proxy IPs
for that hosting environment to obtain the real client IP; otherwise clients may
share the proxy's quota. Do not trust forwarded headers from arbitrary internet clients.

## Local review

1. Run `python -m pytest` and `python -m ruff check .` using the virtual environment.
2. Restart `python -m uvicorn app.main:app --host 127.0.0.1 --port 4000`.
3. Open http://localhost:4000. Analyze a public website and review all sections and
   the expandable JSON. Switch to publishing to enter a message with exactly one
   HTTP(S) link and at most 200 Unicode characters.
4. Publishing requires the confirmation checkbox. It publishes real messages to
   every server-configured platform. Missing credentials produce explicit failures;
   Gemini credentials alone do not enable social publishing. Do not resubmit an
   ambiguous publication without checking the destination for an existing post.

## Render Free web service

Render currently offers Free Python web services. They sleep after 15 minutes
without traffic and can take about a minute to wake. Free quotas and account
eligibility are controlled by Render; choose Free explicitly. If the account
requires payment verification, stop and assess that requirement before proceeding.

1. Push and merge this feature into your own repository's `main` after checks pass.
2. Sign in at https://dashboard.render.com and choose **New > Web Service**.
3. Connect `satya-pverma/dxora-assignment` and choose branch `main`.
4. Choose runtime **Python 3** and instance type **Free**.
5. Set build command to `pip install -r requirements.txt`.
6. Set start command to `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
7. Set health check path to `/health` and add these environment variables in the
   Render dashboard (values are not committed):

| Variable | Value |
| --- | --- |
| `PYTHON_VERSION` | `3.13.5` |
| `LLM_PROVIDER` | `gemini` |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` (worked in the user's local live test) |
| `GEMINI_API_KEY` | Your Gemini key |
| `LLM_TIMEOUT_SECONDS` | `90` |
| `DEMO_ACCESS_KEY` | A long random shared demo password |

8. Add the publishing credentials from `.env.example` only for accounts you intend
   to demonstrate. To restrict destinations, set `POSTING_PLATFORMS` to a JSON
   array, for example `["telegram"]`. No account credentials are sent to the browser.
9. Deploy and wait for the service to become live. Open its `https://...onrender.com`
   URL, expand **Demo access**, and enter the shared demo password. Keep this
   password private and provide it separately to the evaluator when needed.
10. Check `/health`, `/docs`, a live analysis, and an explicitly authorized test
    post. Account permissions and anonymous publication visibility still require
    live verification. Local success does not prove hosting-region API access.

Alternatively, **New > Blueprint** can use the included `render.yaml`. It creates
a Free service, prompts for `GEMINI_API_KEY`, and generates `DEMO_ACCESS_KEY`.
Retrieve that generated value from the service's Environment page for UI access.

The UI and docs remain public. When `DEMO_ACCESS_KEY` is nonempty, both POST
endpoints require an `X-Demo-Key` header (also shown in Swagger). Locally, leaving
it empty preserves the original unauthenticated assignment API. This shared demo
gate is not a multi-user authentication or rate-limiting system.

Never upload `.env`, paste keys into frontend source, or include credentials in
screenshots. Hosting and Gemini free quotas are separate; monitor both dashboards.
No live deployment or publication was performed by adding these files.

References: https://render.com/docs/free and https://render.com/docs/deploy-fastapi
