import pytest

from app.utils.validators import WebsiteError, select_public_address


def test_dual_stack_prefers_ipv4_even_when_ipv6_is_first():
    assert select_public_address(["2606:4700:4700::1111", "1.1.1.1"]) == "1.1.1.1"


def test_ipv6_only_destination_remains_supported():
    assert select_public_address(["2606:4700:4700::1111"]) == "2606:4700:4700::1111"


def test_ipv4_order_is_preserved():
    assert select_public_address(["1.1.1.1", "8.8.8.8"]) == "1.1.1.1"


@pytest.mark.parametrize(
    "addresses",
    [
        [],
        ["1.1.1.1", "10.0.0.1"],
        ["::1", "1.1.1.1"],
        ["invalid", "1.1.1.1"],
        ["2606:4700:4700::1111", "127.0.0.1"],
    ],
)
def test_all_dns_results_must_still_be_public(addresses):
    with pytest.raises(WebsiteError) as error:
        select_public_address(addresses)
    assert error.value.code == "blocked_destination"
