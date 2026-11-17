"""Report configuration readiness without printing credentials or making API calls."""

import argparse

from pydantic import SecretStr, ValidationError

from app.config import Settings

REQUIRED = {
    "OpenAI": ("openai_api_key",),
    "Mastodon": ("mastodon_base_url", "mastodon_access_token"),
    "Bluesky": ("bluesky_pds_url", "bluesky_handle", "bluesky_app_password"),
    "WordPress.com": ("wordpress_site_id", "wordpress_access_token"),
    "Tumblr": ("tumblr_blog_identifier", "tumblr_access_token"),
    "Telegram": ("telegram_bot_token", "telegram_channel_username"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict", action="store_true", help="Exit 1 if any service is missing fields."
    )
    args = parser.parse_args()
    try:
        settings = Settings()
    except ValidationError as exc:
        print("Invalid configuration; review these fields in .env:")
        for error in exc.errors(include_input=False, include_context=False):
            print("- " + ".".join(str(part) for part in error["loc"]).upper())
        return 2
    all_present = True
    for service, fields in REQUIRED.items():
        missing = []
        for field in fields:
            value = getattr(settings, field)
            if isinstance(value, SecretStr):
                value = value.get_secret_value()
            if not value.strip():
                missing.append(field.upper())
        all_present = all_present and not missing
        print(f"{service}: " + ("missing " + ", ".join(missing) if missing else "fields present"))
    print("Presence checks do not verify accounts, permissions, billing, or publication.")
    return 1 if args.strict and not all_present else 0


if __name__ == "__main__":
    raise SystemExit(main())
