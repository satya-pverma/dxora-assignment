# Dxora Assignment

Python/FastAPI implementation of the two practical tests published in
[chivoxai/practical-test](https://github.com/chivoxai/practical-test).

## Status

Project foundation only. The analysis and posting endpoints are not implemented yet.

## Setup

Requires Python 3.11 or later.

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
All development branches and pull requests target this repository. No writes or
pull requests will be made to the assignment's source repository.

Never commit API keys, account tokens, or unsanitized demonstration logs.
