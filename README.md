# Dxora Assignment

Python/FastAPI implementation of the two practical tests published in
[chivoxai/practical-test](https://github.com/chivoxai/practical-test).

## Status

The FastAPI foundation and website extraction service are implemented. The
analysis and posting endpoints are not implemented yet.

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

## Planned APIs

- `POST /link-analysis`: website extraction and structured LLM analysis.
- `POST /posting`: validated messages published through five independent integrations.
- `GET /health`: application health check.

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
working changes are on `feat/website-extraction`, review and publish them:

```powershell
git add README.md docs/PLAN.md app/services app/utils tests/test_website_extractor.py
git commit -m "feat: add bounded website extraction with SSRF protection"
git push -u origin feat/website-extraction
```

Then open a pull request from `feat/website-extraction` into `main` in your own
repository. Review the changes and CI results before merging. Create the next
feature branch from the updated `main` after merging.
