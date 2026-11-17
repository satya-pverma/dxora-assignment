from fastapi import FastAPI

from app.config import get_settings

app = FastAPI(title=get_settings().app_name)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
