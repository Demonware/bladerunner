"""Tests for Bladerunner's progressbar module."""


import os
import sys
from mock import Mock, patch

if sys.version_info <= (2, 7):
    import unittest2 as unittest
else:
    import unittest

if sys.version_info >= (3, 0):
    from io import StringIO
else:
    from StringIO import StringIO

from bladerunner import ProgressBar


class ProgressBarTests(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        self.py3_enabled = sys.version_info > (3,)
        super(ProgressBarTests, self).__init__(*args, **kwargs)

    def setUp(self):
        """Save sys.argv, stdout/err..."""

        self._argv = sys.argv
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.argv = ["progressbar.py"]
        sys.stdout = StringIO()
        sys.stderr = StringIO()

    def tearDown(self):
        """Restore sys.argv, stdout/err..."""

        sys.argv = self._argv
        sys.stdout = self._stdout
        sys.stderr = self._stderr

    def test_setup(self):
        """Ensure we are setting up the pbar correctly."""

        pbar = ProgressBar(10, {"left_padding": "ok then"})
        self.assertEqual(pbar.total, 10)



if __name__ == "__main__":
    unittest.main()
