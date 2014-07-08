"""Some unit tests for Bladerunner's network utilities."""


import pytest

from bladerunner.networking import (
    can_resolve,
    ips_in_subnet,
    _ip_to_binary,
    _binary_to_ip,
)


@pytest.mark.parametrize(
    "network, expected",
    (
        ("10.0.0.0/30", ["10.0.0.1", "10.0.0.2"]),
        ("192.168.16.5/32", ["192.168.16.5"]),
        ("10.16.255.16/255.255.255.255", ["10.16.255.16"]),
    ),
    ids=("simple small", "slash 32", "expanded slash 32"),
)
def test_example_networks(network, expected):
    """Test some example network exact conversions."""

    assert ips_in_subnet(network) == expected


@pytest.mark.parametrize(
    "ipaddr, network",
    (
        ("1.2.3.4", "1.2.3.4/16"),
        ("10.17.29.130", "10.17.29.128/255.255.255.252"),
    ),
    ids=("big network", "expanded subnet"),
)
def test_in_network(ipaddr, network):
    """Ensure the ipaddress is in the network via ips_in_subnet."""

    assert ipaddr in ips_in_subnet(network)


@pytest.mark.parametrize(
    "ipaddr",
    (
        "10.10.256.10/24",
        "10.10.10.0/255.255.-2.0",
        "10.10.10.0/255.255.279.0",
        "10.9.8.0/-3",
        "10.9.8.0/34",
        "1.2.3.4",
    ),
    ids=("invalid ip", "invalid subnet", "mask too big", "invalid slash",
         "oversized slash", "no mask")
)
def test_invalid_returns_none(ipaddr):
    assert ips_in_subnet(ipaddr) is None


def test_can_resolve():
    """Basic test case for the can_resolve function."""

    assert can_resolve("google.com")
    assert not can_resolve("googly.boogly.doodley-do.1234abcd")


def test_converting_back_and_forth():
    """Test converting back to ip from binary."""

    starting = "10.1.2.3"
    made_binary = _ip_to_binary(starting)
    assert _binary_to_ip(made_binary) == starting
