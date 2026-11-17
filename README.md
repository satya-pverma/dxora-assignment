# Dxora Assignment

Python/FastAPI implementation of the two practical tests published in
[chivoxai/practical-test](https://github.com/chivoxai/practical-test).

## Status

Project foundation only. The analysis and posting endpoints are not implemented yet.

## Setup

Requires Python 3.11 or later.
Use a Python installation permitted by your machine's application policy.
If `python` is unavailable, replace it below with your approved interpreter path.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

API documentation: http://localhost:4000/docs

```powershell
python -m pytest
python -m ruff check .
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

## Manual GitHub workflow

The foundation is published on `main`. The remote is configured as
`https://github.com/satya-pverma/dxora-assignment.git`.

Each subsequent milestone uses a separate branch and pull request. For this
research milestone, review and publish the changes:

```powershell
git add README.md docs/PLAN.md docs/INTEGRATION_RESEARCH.md
git commit -m "docs: research publishing APIs and LLM selection"
git push -u origin docs/integration-research
```

Then open a pull request from `docs/integration-research` into `main` in your own
repository. Review the changes and CI results before merging. Create the next
feature branch from the updated `main` after merging.
