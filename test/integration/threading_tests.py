"""Confirm Bladerunner's threading features.

The following environment must exist:

    HOST is real, and listening for SSH on its address (name or otherwise)
    USER_NAME has a ssh key in the authorized_keys file on HOST

If HOST does not resolve, all tests will be skipped
"""


import sys
import time
from tornado import gen

if sys.version_info <= (2, 7):
    import unittest2 as unittest
else:
    import unittest

from bladerunner.base import Bladerunner
from bladerunner.networking import can_resolve


class ThreadingTests(unittest.TestCase):
    HOST = "some_test_host_you_have_root_access_on"
    USER_NAME = "root"

    def setUp(self):
        """Set up the bladerunner options dictionary."""

        self.should_fail = False
        self.options = {"username": ThreadingTests.USER_NAME}

    def _parse_results(self, results):
        """parse the results dictionary returned from tests."""

        # check for login failures
        self.assertIsInstance(results, list)
        for result_set in results:
            if ThreadingTests.HOST in result_set.get("name"):
                for command, result in result_set["results"]:
                    if "login" in command:
                        if self.should_fail:
                            self.assertIn(
                                "err",
                                result,
                                "login did not error as expected",
                            )
                        else:
                            self.assertNotIn(
                                "err",
                                result,
                                "error logging in. are ssh keys setup?",
                            )

    @unittest.skipIf(not can_resolve(HOST), "Can't resolve {0}".format(HOST))
    def test_get_run_thread(self):
        """confirm that the run_threaded method returns instantly."""

        runner = Bladerunner(self.options)
        start_time = time.time()
        thread = runner.run_threaded(
            "echo 'hello world'",
            ThreadingTests.HOST,
            callback=self._parse_results,
        )
        self.assertTrue(time.time() - start_time < 2)
        thread.join()

    @unittest.skipIf(not can_resolve(HOST), "Can't resolve {0}".format(HOST))
    @gen.engine
    def test_use_with_callback(self, callback=None):
        """use the thread in a gen.Task."""

        runner = Bladerunner(self.options)
        results = yield gen.Task(
            runner.run_threaded,
            "echo 'hello world'",
            ThreadingTests.HOST,
        )
        self._parse_results(results)

    @unittest.skipIf(not can_resolve(HOST), "Can't resolve {0}".format(HOST))
    def test_unknown_host_errors(self):
        """test logging into an unknown host results in an error."""

        self.should_fail = True
        runner = Bladerunner(self.options)
        results = runner.run("echo 'hi'", "xyz1234.qwertasdfzxcvpoiu.12awol")
        self._parse_results(results)


if __name__ == "__main__":
    unittest.main()
