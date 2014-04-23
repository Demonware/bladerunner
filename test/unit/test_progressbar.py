"""Tests for Bladerunner's progressbar module."""


import pytest
from mock import patch

from bladerunner import ProgressBar


def test_setup(capfd):
    """Ensure we are setting up the pbar correctly."""

    pbar = ProgressBar(10, {"left_padding": "ok then"})
    assert pbar.total == 10
    pbar.setup()
    out, _  = capfd.readouterr()
    assert out.startswith("ok then")


@pytest.mark.parametrize(
    "options", 
    [
        {"width": None},
        {"width": 0},
        {"width": False},
        {},
    ],
    ids=["None", "0", "False", "empty"],
)
def test_width_is_none(options):
    """Regression test for 4.0.2 progressbar display bug."""
    
    width_patch = patch(
        "bladerunner.progressbar.get_term_width", 
        return_value=123,
    )
    with width_patch as patched_width:
        pbar = ProgressBar(10, options)
        patched_width.assert_called_once()
    assert pbar.total_width == 123

