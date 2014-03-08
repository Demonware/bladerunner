"""Tests for Bladerunner as a package."""


import unittest

import bladerunner


class PackageTests(unittest.TestCase):
    def test_back_compat_methods(self):
        """Ensure the top level functions/methods/objects don't change."""

        package_level_exports = [
            "Bladerunner",
            "cmdline_entry",
            "cmdline_exit",
            "ProgressBar",
            "get_term_width",
            "consolidate",
            "pretty_results",
            "csv_results",
        ]

        for export in package_level_exports:
            self.assertIn(export, dir(bladerunner))


if __name__ == "__main__":
    unittest.main()
