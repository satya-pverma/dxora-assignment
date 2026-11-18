"""Read-only MongoDB/decryption check. Never refreshes tokens or publishes."""

from app.config import Settings
from app.platforms.base import PlatformError
from app.services.posting_service import ERROR_MESSAGES
from app.services.tumblr_tokens import (
    REFRESH_FAILURES,
    TumblrTokenStore,
    require_refresh_config,
    storage_error_code,
    token_collection,
)


def main():
    try:
        settings = Settings()
        require_refresh_config(settings)
        with token_collection(settings) as collection:
            store = TumblrTokenStore(settings, collection)
            record = collection.find_one({"_id": store.record_id})
            print("MongoDB connection and record lookup: OK")
            if record is None:
                print("No token record for this app/blog. Initialize it before testing renewal.")
                return 1
            for field in ("access_token", "refresh_token"):
                store.cipher.decrypt(record[field].encode())
            print("Stored token decryption: OK")
            print("Refresh state: " + (
                record["state"] if record.get("state") in {"ready", "refreshing", "reauthorize"}
                else "invalid"
            ))
            if record.get("last_error") in REFRESH_FAILURES:
                print("Last renewal failure: " + ERROR_MESSAGES[record["last_error"]])
            return 0 if record.get("state") == "ready" else 1
    except Exception as exc:
        code = exc.code if isinstance(exc, PlatformError) else storage_error_code(exc)
        print(ERROR_MESSAGES.get(code, "Token storage check failed. Review configuration."))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
