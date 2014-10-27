"""Tests for Bladerunner's progressbar module."""


import os
import pytest
from mock import call
from mock import Mock
from mock import patch

from bladerunner import progressbar
from bladerunner.progressbar import ProgressBar

try:
    import termios
except ImportError:
    pass


def test_setup(capfd):
    """Ensure we are setting up the pbar correctly."""

    pbar = ProgressBar(10, {"left_padding": "ok then"})
    assert pbar.total == 10
    pbar.setup()
    out, _ = capfd.readouterr()
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
        assert patched_width.called
    assert pbar.total_width == 123


def test_default_options():
    """Ensure the configuration when no options are given."""

    with patch.object(progressbar, "get_term_width", return_value=10) as p_get:
        ProgressBar(10)
    assert p_get.called


@pytest.mark.parametrize("style", (-1, 9000, "bananas"))
def test_invalid_style(style):
    """If an invalid style integer is passed, assume style 0."""

    pbar = ProgressBar(10, {"style": style})
    assert pbar.style == 0


@pytest.mark.parametrize("updates", (10, 100, 9001, 50000))
def test_counters_reduce_width(updates):
    """When show counters is used, the total width is reduced."""

    pbar = ProgressBar(updates, {"show_counters": True, "width": 40})
    # reduced by 8 here, len(updates) * 2, space, slash, left and right padding
    assert pbar.width == 40 - ((len(str(updates)) * 2) + 4)


def test_setup(capfd):
    """Ensure we create the initial empty bar correctly."""

    pbar = ProgressBar(10, {"width": 20, "style": 1})
    pbar.setup()
    stdout, _ = capfd.readouterr()
    assert stdout == "{                  }"


def test_setup_with_counters(capfd):
    """Make sure we have 0/count when the bar is setup."""

    pbar = ProgressBar(10, {"show_counters": True, "width": 25})
    pbar.setup()
    stdout, _ = capfd.readouterr()
    assert stdout == "[                  ] 0/10"


def test_update(capfd):
    """Verify that the progressbar is updating correctly."""

    pbar = ProgressBar(4, {"width": 8})
    pbar.setup()
    stdout, _ = capfd.readouterr()
    assert "[      ]" in stdout
    pbar.update()
    stdout, _ = capfd.readouterr()
    assert "[=-    ]" in stdout
    pbar.update()
    stdout, _ = capfd.readouterr()
    assert "[===   ]" in stdout
    pbar.update()
    stdout, _ = capfd.readouterr()
    assert "[====- ]" in stdout
    pbar.update()
    stdout, _ = capfd.readouterr()
    assert "[======]" in stdout

    # over-updating should do nothing
    pbar.update()
    stdout, _ = capfd.readouterr()
    assert stdout == ""


def test_update_with_counters(capfd):
    """Test updating the progressbar with counters."""

    pbar = ProgressBar(4, {"style": 1, "width": 12, "show_counters": True})
    pbar.setup()
    stdout, _ = capfd.readouterr()
    assert "{      } 0/4" in stdout
    pbar.update()
    stdout, _ = capfd.readouterr()
    assert "{*-    } 1/4" in stdout
    pbar.update()
    stdout, _ = capfd.readouterr()
    assert "{***   } 2/4" in stdout
    pbar.update()
    stdout, _ = capfd.readouterr()
    assert "{****- } 3/4" in stdout
    pbar.update()
    stdout, _ = capfd.readouterr()
    assert "{******} 4/4" in stdout

    # over-updating should do nothing
    pbar.update()
    stdout, _ = capfd.readouterr()
    assert stdout == ""


def test_update_quarters(capfd):
    """Ensure the progressbar updates on the quarter completion of a char."""

    pbar = ProgressBar(5, {"width": 3})
    pbar.setup()
    stdout, _ = capfd.readouterr()
    assert "[ ]" in stdout
    pbar.update()
    stdout, _ = capfd.readouterr()
    assert "[/]" in stdout
    pbar.update()
    stdout, _ = capfd.readouterr()
    assert "[-]" in stdout
    pbar.update()
    stdout, _ = capfd.readouterr()
    assert "[-]" in stdout
    pbar.update()
    stdout, _ = capfd.readouterr()
    assert "[\\]" in stdout
    pbar.update()
    stdout, _ = capfd.readouterr()
    assert "[=]" in stdout


def test_clear(capfd):
    """Ensure we print whitespace over the bar and carriage return."""

    pbar = ProgressBar(10, {"width": 20})
    pbar.clear()
    stdout, _ = capfd.readouterr()
    assert "                    " in stdout


@pytest.mark.skipif(not "termios" in globals(), reason="termios not found")
def test_get_term_width():
    """Verify the calls made to attempt to guess the terminal width."""

    with patch.object(progressbar.struct, "unpack", return_value=None) as p_un:
        with patch.object(progressbar.fcntl, "ioctl", return_value=10) as p_io:
            assert progressbar.get_term_width() == 80  # default value

    calls_to_verify = [
        call(0, termios.TIOCGWINSZ, "1234"),
        call(1, termios.TIOCGWINSZ, "1234"),
        call(2, termios.TIOCGWINSZ, "1234"),
    ]

    try:
        os_fd = os.open(os.ctermid(), os.O_RDONLY)
        calls_to_verify.append(call(os_fd, termios.TIOCGWINSZ, "1234"))
        calls_made = 4
    except OSError:
        calls_made = 3
    else:
        os.close(os_fd)
    finally:
        assert p_un.call_count == calls_made
        assert p_io.mock_calls == calls_to_verify


@pytest.mark.skipif(not "termios" in globals(), reason="termios not found")
def test_get_term_with_os_err():
    """Simulate an exception from os.ctermid, should be ignored."""

    with patch.object(progressbar.os, "ctermid", side_effect=OSError("mock")):
        with patch.object(progressbar.fcntl, "ioctl", return_value=10) as p_io:
            assert progressbar.get_term_width() == 80

    assert p_io.mock_calls == [
        call(0, termios.TIOCGWINSZ, "1234"),
        call(1, termios.TIOCGWINSZ, "1234"),
        call(2, termios.TIOCGWINSZ, "1234"),
    ]


def test_help_msg():
    """Ensure the content of the pbar cmd line help message."""

    with pytest.raises(SystemExit) as sys_exit:
        progressbar.cmd_line_help("faked")
    error = sys_exit.exconly()

    for search in ["count", "delay", "help", "hide-counters", "style", "width",
                   "left-padding", "right-padding", "faked", "Bladerunner"]:
        assert search in error


def test_cmd_line_arguments():
    """Ensure we return the options from the argparser correctly."""

    fake_args = ["--count", "10", "--delay", "20", "--style", "3", "--width",
                 "40", "--left-padding", "left", "--right-padding", "right"]

    ret = progressbar.cmd_line_arguments(fake_args)

    assert ret.count == 10
    assert ret.delay == 20.0
    assert ret.style == 3
    assert ret.width == 40
    assert ret.left_padding == "left"
    assert ret.right_padding == "right"


def test_cmd_line_help():
    """Ensure we raise sysexit when --help is used."""

    with pytest.raises(SystemExit):
        progressbar.cmd_line_arguments(["--help"])


def test_cmd_line_demo():
    """Ensure we set up the cmd line demo correctly."""

    fake_args = ["--count", "10", "--delay", "20", "--style", "3", "--width",
                 "40", "--left-padding", "left", "--right-padding", "right",
                 "--hide-counters"]

    pbar = Mock()
    # simulate throwing ^c after the third update call
    pbar.update = Mock(side_effect=iter([None, None, None, KeyboardInterrupt]))
    with patch.object(progressbar, "ProgressBar", return_value=pbar) as p_pbar:
        with patch.object(progressbar.time, "sleep") as p_sleep:
            with patch.object(progressbar.sys.stdout, "write") as p_write:
                progressbar.cmd_line_demo(fake_args)

    p_pbar.assert_called_once_with(10, {
        "style": 3,
        "width": 40,
        "show_counters": False,
        "left_padding": "left",
        "right_padding": "right",
    })

    assert p_sleep.call_count == 4
    for p_sleep_call in p_sleep.mock_calls:
        assert p_sleep_call == call(20.0)
    p_write.assert_called_once_with("\n")
