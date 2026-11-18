import pytest

from app.services.analysis_service import match_source_quote
from app.services.llm_service import provider_schema
from app.services.website_extractor import ExtractedWebsite


@pytest.mark.parametrize(
    ("quote", "text", "expected"),
    [
        ("Find a plug. Book a slot.", "Find a plug.\nBook a slot.", "Find a plug.\nBook a slot."),
        ("Live plug status", "Live\u00a0plug\tstatus", "Live\u00a0plug\tstatus"),
        ("Book a slot.", "Features: Book a slot. Today.", "Book a slot."),
        ("We build spacecraft.", "We offer web design.", None),
        ("Find a charger", "Find a plug", None),
        ("Find ... plug", "Find a charging plug", None),
        ("book a slot", "Book a slot", None),
        ("", "Some evidence", None),
    ],
)
def test_quote_matching_preserves_literal_evidence(quote, text, expected):
    assert match_source_quote(quote, text) == expected


def test_provider_quote_choices_are_bounded_literal_source_excerpts():
    text = "Find a plug.\nBook a slot.\n" + "\n".join(
        f"Service {i}: " + "x" * 400 for i in range(300)
    )
    website = ExtractedWebsite(
        requested_url="https://example.com", final_url="https://example.com",
        title="Example", meta_description="", headings=[], text=text, truncated=False,
    )
    choices = provider_schema(website)["$defs"]["Service"]["properties"]["source_quote"]["enum"]
    assert choices[0] is None
    assert "Book a slot." in choices
    assert len(choices) <= 257
    assert all(choice in text and len(choice) <= 300 for choice in choices[1:])
