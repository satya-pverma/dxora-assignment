"""Extract one explicit HTTP(S) CTA without fetching the destination."""

import re
from dataclasses import dataclass

from pydantic import HttpUrl, TypeAdapter, ValidationError

URL_ADAPTER = TypeAdapter(HttpUrl)
SCHEME_PATTERN = re.compile(r"\b([a-z][a-z0-9+.-]*)://", re.IGNORECASE)
LINK_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


@dataclass(frozen=True)
class CTALink:
    start: int
    end: int
    url: str


def extract_cta_link(message: str) -> CTALink:
    schemes = list(SCHEME_PATTERN.finditer(message))
    links = list(LINK_PATTERN.finditer(message))
    if len(schemes) != 1 or len(links) != 1:
        raise ValueError("Include exactly one explicit HTTP(S) CTA link.")
    if schemes[0].group(1).lower() not in {"http", "https"}:
        raise ValueError("The CTA link must use HTTP or HTTPS.")
    value = links[0].group().rstrip(".,!;")
    # Permit surrounding prose parentheses without removing balanced URL characters.
    for closing, opening in ((")", "("), ("]", "["), ("}", "{")):
        while value.endswith(closing) and value.count(closing) > value.count(opening):
            value = value[:-1]
    if "\\" in value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("The CTA link contains invalid characters.")
    try:
        url = URL_ADAPTER.validate_python(value)
    except ValidationError as exc:
        raise ValueError("The CTA link must be a valid HTTP(S) URL.") from exc
    if url.username or url.password:
        raise ValueError("The CTA link must not contain credentials.")
    return CTALink(links[0].start(), links[0].start() + len(value), str(url))


def extract_cta_url(message: str) -> str:
    return extract_cta_link(message).url
