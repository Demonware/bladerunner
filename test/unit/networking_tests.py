"""Some unit tests for Bladerunner's network utilities."""


import sys

if sys.version_info <= (2, 7):
    import unittest2 as unittest
else:
    import unittest

from bladerunner.networking import (
    can_resolve,
    ips_in_subnet,
    _ip_to_binary,
    _binary_to_ip,
)


class TestSubnetConversion(unittest.TestCase):
    def test_simple_small(self):
        subnet = "10.0.0.0/30"
        should_be = ["10.0.0.1", "10.0.0.2"]
        self.assertEqual(ips_in_subnet(subnet), should_be)

    def test_expanded_subnet(self):
        starting = "10.17.29.128/255.255.255.252"
        self.assertIn("10.17.29.130", ips_in_subnet(starting))

    def test_converting_back_and_forth(self):
        starting = "10.1.2.3"
        made_binary = _ip_to_binary(starting)
        self.assertEqual(_binary_to_ip(made_binary), starting)

    def test_ip_with_no_mask_returns_none(self):
        starting = "1.2.3.4"
        members = ips_in_subnet(starting)
        self.assertEqual(members, None)

    def test_big_network(self):
        starting = "1.2.3.4"
        members = ips_in_subnet("{0}/16".format(starting))
        self.assertIn(starting, members)

    def test_slash_thirtytwo(self):
        starting = "192.168.16.5/32"
        should_be = ["192.168.16.5"]
        self.assertEqual(ips_in_subnet(starting), should_be)

    def test_expanded_slash_thirty_two(self):
        starting = "10.16.255.16/255.255.255.255"
        should_be = ["10.16.255.16"]
        self.assertEqual(ips_in_subnet(starting), should_be)

    def test_invalid_ips_returns_none(self):
        starting = "10.10.256.10/24"
        self.assertEqual(ips_in_subnet(starting), None)

    def test_invalid_subnet_returns_none(self):
        starting = "10.10.10.0/255.255.-2.0"
        self.assertEqual(ips_in_subnet(starting), None)

    def test_subnet_mask_too_large_returns_none(self):
        starting = "10.10.10.0/255.255.279.0"
        self.assertEqual(ips_in_subnet(starting), None)

    def test_invalid_slash_returns_none(self):
        starting = "10.9.8.0/-3"
        self.assertEqual(ips_in_subnet(starting), None)

    def test_oversized_slash_returns_none(self):
        starting = "10.9.8.0/34"
        self.assertEqual(ips_in_subnet(starting), None)

    def test_can_resolve(self):
        self.assertTrue(can_resolve("google.com"))
        self.assertFalse(can_resolve("googly.boogly.doodley-do.1234abcd"))

if __name__ == "__main__":
    unittest.main()
