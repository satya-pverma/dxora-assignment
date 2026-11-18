"""List text-generation model IDs without generating content or printing secrets."""

import httpx
from pydantic import ValidationError

from app.config import Settings


def main() -> int:
    try:
        settings = Settings()
    except ValidationError:
        print("Invalid local configuration; run scripts.check_credentials to identify fields.")
        return 2
    key = settings.gemini_api_key.get_secret_value().strip()
    if not key:
        print("GEMINI_API_KEY is missing.")
        return 1
    try:
        with httpx.Client(timeout=10, trust_env=False, follow_redirects=False) as client:
            page_token = None
            for _ in range(10):
                response = client.get(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    headers={"x-goog-api-key": key},
                    params={"pageToken": page_token} if page_token else None,
                )
                if response.status_code != 200:
                    print(
                        f"Model listing failed (HTTP {response.status_code}); "
                        "check AI Studio access."
                    )
                    return 1
                data = response.json()
                for model in data.get("models", []):
                    if "generateContent" in model.get("supportedGenerationMethods", []):
                        print(model["name"].removeprefix("models/"))
                page_token = data.get("nextPageToken")
                if not page_token:
                    print(
                        "Listed models do not guarantee free quota; "
                        "check AI Studio Rate Limit."
                    )
                    return 0
            print("Additional model pages omitted.")
            return 0
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        print("Model listing failed; check connectivity and API access. No secret details printed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
