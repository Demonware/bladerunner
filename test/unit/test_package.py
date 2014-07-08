"""Tests for Bladerunner as a package."""


import pytest

import bladerunner


@pytest.fixture
def dir_bladerunner():
    """Returns the dir() of bladerunner as a package."""

    return dir(bladerunner)


@pytest.mark.parametrize(
    "method",
    [
        "Bladerunner",
        "cmdline_entry",
        "cmdline_exit",
        "ProgressBar",
        "get_term_width",
        "consolidate",
        "pretty_results",
        "csv_results",
    ],
)
def test_package_exports(method, dir_bladerunner):
    """Ensure the top level functions/methods/objects don't change."""

    assert method in dir_bladerunner
