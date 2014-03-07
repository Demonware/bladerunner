"""Base testing class."""


import unittest


class BladerunnerTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        """Setattr on self to give assertIn if required."""

        # add more as needed
        back_compat_methods = [
            "assertIn",
            "assertNotIn",
            "assertIsInstance",
            "assertIsInstance",
        ]
        for method in back_compat_methods:
            if not hasattr(self, method):
                setattr(
                    self,
                    method,
                    getattr(self, "_{0}BackCompat".format(method))
                )
        super(BladerunnerTest, self).__init__(*args, **kwargs)

    def _assertInBackCompat(self, first, second, msg=None):
        """Backwards compatability to provide assertIn to older unittest."""

        return self.assertTrue(
            first in second,
            msg or "{0} not found in {1}".format(first, second),
        )

    def _assertNotInBackCompat(self, first, second, msg=None):
        """Backwards compatability to provide assertNotIn to older unittest."""

        return self.assertTrue(
            first not in second,
            msg or "{0} found in {1}".format(first, second),
        )

    def _assertIsInstanceBackCompat(self, first, second, msg=None):
        """Backwards compatability to provide IsInstance to older unittest."""

        try:
            result = self.assertTrue(
                isinstance(first, second),
                msg or "{0} is not an instance of {1}".format(first, second),
            )
        except Exception as error:
            result = self.fail(
                msg or "isinstance({0}, {1}) errored: {2}".format(
                    first, second, error)
            )
        finally:
            return result

    def _assertIsNotInstanceBackCompat(self, first, second, msg=None):
        """Backwards compatability to give IsNotInstance to older unittest."""

        try:
            result = self.assertFalse(
                isinstance(first, second),
                msg or "{0} is an instance of {1}".format(first, second),
            )
        except Exception as error:
            result = self.fail(
                msg or "isinstance({0}, {1}) errored: {2}".format(
                    first, second, error)
            )
        finally:
            return result
