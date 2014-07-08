"""Confirm Bladerunner's threading features.

These tests will not run unless you alter the settings in dictionary return of
the function 'config'. The host used in that dictionary must resolve, the user
must be exist on the remote, and the default ssh key of the user running this
test must be in the authorized_keys file on the remote host for the test user.
"""


import time
import pytest

from tornado import gen

from bladerunner.base import Bladerunner
from bladerunner.networking import can_resolve


def config():
    """Integration test config. Override the dictionary to run the tests."""

    return {
        "host": "some_test_host_you_have_access_to",
        "user_name": "some_remote_user_with_your_key_in_authorized_keys",
    }


@pytest.fixture(scope="session")
def settings():
    """Gives the config to the tests if the host resolves, or skips."""

    conf = config()
    if not can_resolve(conf["host"]):
        pytest.skip("cannot resolve {0}".format(conf["host"]))

    return conf


def parse_results(results, should_fail=False):
    """parse the results dictionary returned from tests."""

    # check for login failures
    assert isinstance(results, list)

    for result_set in results:
        if config()["host"] in result_set.get("name"):
            for command, result in result_set["results"]:
                if "login" in command:
                    if should_fail:
                        assert "err" in result, "did not receive expected err"
                    else:
                        assert not "err" in result, "login err. is ssh setup?"


def parse_for_success(results):
    """Parse the results for the absense of errors."""

    return parse_results(results)


def parse_for_failure(results):
    """Parse the results for an error."""

    return parse_results(results, should_fail=True)


def test_get_run_thread(settings):
    """Confirm that the run_threaded method returns instantly."""

    runner = Bladerunner(settings)
    start_time = time.time()
    thread = runner.run_threaded(
        "echo 'hello world'",
        settings["host"],
        callback=parse_results,
    )
    assert time.time() - start_time < 2
    thread.join()


def test_use_with_callback(settings):
    """use the thread in a gen.Task."""

    @gen.engine
    def _run_test(callback=None):
        """Shim for gen.engine with pytest."""

        runner = Bladerunner(settings)
        results = yield gen.Task(
            runner.run_threaded,
            "echo 'hello world'",
            settings["host"],
        )
        parse_for_success(results)
        if callback:
            callback()

    _run_test()


def test_unknown_host_errors(settings):
    """test logging into an unknown host results in an error."""

    runner = Bladerunner(settings)
    results = runner.run("echo 'hi'", "xyz1234.qwertasdfzxcvpoiu.12awol")
    parse_for_failure(results)
