"""Base testing class."""


import unittest


class BladerunnerTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        """Setattr on self to give assertIn if required."""

        if not hasattr(self, "assertIn"):
            setattr(self, "assertIn", self._assertInBackCompat)
        super(BladerunnerTest, self).__init__(*args, **kwargs)

    def _assertInBackCompat(self, first, second):
        """Backwards compatability to provide assertIn to older unittest."""

        return self.assertTrue(
            first in second,
            "{} not found in {}".format(first, second),
        )
