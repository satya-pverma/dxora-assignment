"""Initialize encrypted Tumblr tokens without posting or refreshing them."""

import argparse

from app.config import Settings
from app.services.tumblr_tokens import TumblrTokenStore, require_refresh_config, token_collection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replace", action="store_true",
        help="Replace the stored record with freshly authorized .env tokens. Stop posting first.",
    )
    args = parser.parse_args()
    try:
        settings = Settings()
        require_refresh_config(settings)
        with token_collection(settings) as collection:
            TumblrTokenStore(settings, collection).seed(replace=args.replace)
    except Exception:
        print("Token setup failed. Check MongoDB, encryption and Tumblr credential settings.")
        return 1
    print("Encrypted Tumblr tokens initialized. No refresh or publication was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
