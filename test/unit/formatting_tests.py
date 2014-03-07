#coding: utf-8
"""Unit tests for Bladerunner's output formatting."""


from __future__ import unicode_literals

import sys
import unittest

if sys.version_info.major > 2:
    from io import StringIO
else:
    from StringIO import StringIO

from bladerunner import formatting


class TestFormatting(unittest.TestCase):
    def setUp(self):
        """Set up a StringIO capture on sys.stdout and a dummy result set."""

        self._stdout = sys.stdout
        sys.stdout = StringIO()

        self.result_set_a = [
            ("echo 'hello world'", "hello world"),
            ("uptime", "00:22:07 up 497 days,  6:30, 11 users,  load average: "
                       "0.00, 0.00, 0.00"),  # whatup.
        ]

        self.result_set_b = [
            ("echo 'hello world'", "hello world"),
            ("cat cat", "cat: cat: No such file or directory")
        ]

        self.fake_results = [
            {"name": "server_a_1", "results": self.result_set_a},
            {"name": "server_a_2", "results": self.result_set_a},
            {"name": "server_a_3", "results": self.result_set_a},
            {"name": "server_a_4", "results": self.result_set_a},
            {"name": "server_b_1", "results": self.result_set_b},
            {"name": "server_b_2", "results": self.result_set_b},
            {"name": "server_b_3", "results": self.result_set_b},
            {
                "name": "server_c_1",
                "results": self.result_set_a + self.result_set_b,
            },
        ]

    def tearDown(self):
        """Reset stdout."""

        sys.stdout = self._stdout

    def test_no_empties(self):
        """No empties should return the same list without empty elements."""

        starting = ["something", "", "else", None, "and", "things", "", r""]
        self.assertEqual(
            formatting.no_empties(starting),
            ["something", "else", "and", "things"],
        )

    def test_format_output(self):
        """Should remove the first, last, and any line with command in it."""

        command = "super duper secret command"
        fake_output = [
            "someshell# {}".format(command),
            "lots of interesting",
            "output n stuff",
            "someshell#",
        ]
        self.assertEqual(
            formatting.format_output("\n".join(fake_output), command),
            "lots of interesting\noutput n stuff",
        )

    def test_command_in_second_line(self):
        """Long commands and small terminals can lead to leakage."""

        command = (
            "super secret and long rediculous command that receives so many "
            "arguments it spills over into the next line"
        )
        fake_output = [
            "someshell# {}\n{}".format(command[:50], command[50:]),
            "lots of interesting",
            "output n stuff",
            "someshell#",
        ]
        self.assertEqual(
            formatting.format_output("\n".join(fake_output), command),
            "lots of interesting\noutput n stuff",
        )

    def test_unknown_returns_line(self):
        """Let it fail if the shell cant display it if we can't decode."""

        starting = "Everybody loves a 🍔!"
        self.assertEqual(formatting.format_line(starting), starting)

    def test_consolidte_results(self):
        """Consolidate should merge matching server result sets."""

        expected_groups = [
            ["server_a_1", "server_a_2", "server_a_3", "server_a_4"],
            ["server_b_1", "server_b_2", "server_b_3"],
            ["server_c_1"],
        ]

        for result_set in formatting.consolidate(self.fake_results):
            self.assertIn("names", result_set)
            self.assertIsInstance(result_set["names"], list)
            self.assertNotIn("name", result_set)
            self.assertIn(result_set["names"], expected_groups)

    def test_csv_results(self):
        """Ensure CSV results print correctly."""

        formatting.csv_results(self.fake_results, {})
        stdout = sys.stdout.getvalue().strip()
        self.assertIn("server,command,result", stdout)
        for server in self.fake_results:
            self.assertIn(server["name"], stdout)
            for _, results in server["results"]:
                self.assertIn(results, stdout)

    def test_csv_custom_char(self):
        """Ensure you can specify the char used in csv_results."""

        options = {"csv_char": "@"}
        formatting.csv_results(self.fake_results, options)
        stdout = sys.stdout.getvalue().strip()
        self.assertIn("server@command@result", stdout)
        for server in self.fake_results:
            self.assertIn(server["name"], stdout)
            for _, results in server["results"]:
                self.assertIn(results, stdout)

    def test_csv_on_consolidated(self):
        """CSV results should still work post consolidation."""

        result_set = formatting.consolidate(self.fake_results)
        formatting.csv_results(result_set, {})
        stdout = sys.stdout.getvalue().strip()
        self.assertIn("server,command,result", stdout)
        for server in result_set:
            self.assertIn(" ".join(server["names"]), stdout)
            for _, results in server["results"]:
                self.assertIn(results, stdout)


if __name__ == "__main__":
    unittest.main()
