"""Tests for the command line entry."""


import os
import sys
import pytest
import getpass
import tempfile
from mock import Mock
from mock import patch

from bladerunner import cmdline
from bladerunner.base import Bladerunner
from bladerunner.cmdline import (
    argparse_unlisted,
    cmdline_entry,
    cmdline_exit,
    get_commands,
    get_passwords,
    get_servers,
    setup_output_file,
)


@pytest.fixture
def option_mismatches():
    """Returns dict of command line flags => br options."""

    return {
        "jump_host": "jumpbox",
        "jump_user": "jumpbox-user",
        "jump_port": "jumpbox-port",
        "jump_password": "jumpbox-password",
        "password_safety": "no-password-check",
        "passwd_prompts": "match",
        "shell_prompts": "match",
        "extra_prompts": "match",
        "csv_char": "csv-separator",
        "progressbar": "--",
        "cmd_timeout": "command-timeout",
        "width": "--",
    }


@pytest.fixture(scope="function", autouse=True)
def setup():
    """Reset sys.argv"""

    sys.argv = ["bladerunner"]


def test_get_help():
    """Ensure we raise SystemExit with a help message."""

    sys.argv.append("--help")
    dummy_runner = Bladerunner()
    with pytest.raises(SystemExit):
        with patch.object(cmdline, "print_help") as helper:
            cmdline_entry()

    assert helper.called


def test_get_help_contents(option_mismatches, capfd):
    """Check the contents of --help includes all options."""

    sys.argv.append("--help")
    dummy_runner = Bladerunner()

    with pytest.raises(SystemExit):
        cmdline_entry()

    # help is printed to stdout
    message, _ = capfd.readouterr()

    for option in dummy_runner.options:
        if option in option_mismatches:
            option_key = option_mismatches[option]
        else:
            option_key = option

        assert option_key.replace("_", "-") in message


def test_get_settings():
    """You should get a dump of the settings if you use --settings."""

    sys.argv.extend(["--settings", "-Nn", "uptime", "somehost.com"])
    with pytest.raises(SystemExit) as error:
        cmdline_entry()

    message = error.exconly()

    should_finds = [
        "'debug': False",
        "'password_safety': False",
        "'password': None",
    ]

    for should_find in should_finds:
        assert should_find in message


def test_fixed_width_with_csv():
    """Should raise a usage error."""

    sys.argv.extend(["--fixed", "--csv", "uptime", "somehost"])
    with pytest.raises(SystemExit):
        cmdline_entry()


def test_no_servers_raises():
    """Should get an error unless both command and server are supplied."""

    sys.argv.append("uptime")
    with pytest.raises(SystemExit):
        cmdline_entry()


def test_ssh_key_passing():
    """Ensure we can provide a non-standard ssh key path."""

    sys.argv.extend(["--ssh-key", "/home/bob/ssh_key", "-nN", "w", "host"])
    cmds, servers, options = cmdline_entry()
    assert options["ssh_key"] == "/home/bob/ssh_key"
    assert ["host"] == servers
    assert ["w"] == cmds
    assert options["username"] is None


def test_username_passing():
    """Ensure we can use a username that's not our own."""

    sys.argv.extend(["-u", "joebob", "-nN", "w", "host"])
    cmds, servers, options = cmdline_entry()
    assert options["username"] == "joebob"
    assert ["host"] == servers
    assert ["w"] == cmds


def test_jumpbox_username_passing():
    """Ensure we can use a jumpbox username that's not our own."""

    sys.argv.extend(["-U", "joebob", "-nN", "w", "host"])
    cmds, servers, options = cmdline_entry()
    assert options["jump_user"] == "joebob"
    assert ["host"] == servers
    assert ["w"] == cmds
    assert options["username"] is None


def test_debugging():
    """Ensure debug with no int sets debug to True."""

    sys.argv.extend(["--debug", "-nN", "w", "host"])
    cmds, servers, options = cmdline_entry()
    assert options["debug"]
    assert ["host"] == servers
    assert ["w"] == cmds
    assert options["username"] is None


def test_csv_becomes_set_from_char():
    """If the csv_char is non-standard, enable csv output."""

    sys.argv.extend(["--csv-separator", "j", "-nN", "w", "host"])
    cmds, servers, options = cmdline_entry()
    assert ["host"] == servers
    assert ["w"] == cmds
    assert options["style"] == -1
    assert options["csv_char"] == "j"


def test_invalid_style_is_csv():
    """If the user supplies an invalid style int, should default to CSV."""

    # <= py2.6 doesn't like multi-with statements
    with pytest.raises(SystemExit):
        with patch.object(cmdline, "csv_results") as csv:
            cmdline_exit([], {"style": 1234})

    assert csv.called


def test_valid_style_is_pretty():
    """If style is valid, the output should be parsed by pretty_results."""

    with pytest.raises(SystemExit):
        with patch.object(cmdline, "pretty_results") as pretty:
            cmdline_exit([], {"style": 2})

    assert pretty.called


def test_unicode_errors_revert_csv():
    """Fake an output issue to ensure fallback to CSV results."""

    results = [{"name": "fake", "results": [("echo wat", "wat")]}]

    if sys.version_info > (3,):
        second = "unichr"
    else:
        second = unicode("unichr")

    mock_error = Mock(
        side_effect=UnicodeEncodeError("utf-8", second, 1, 1, "chars")
    )

    with pytest.raises(SystemExit):
        with patch.object(cmdline, "csv_results") as csv:
            with patch.object(cmdline, "pretty_results", new=mock_error):
                cmdline_exit(results, {"style": 2})

    assert csv.called


def test_reading_command_file():
    """Make a tempfile, ensure it's read into the commands list."""

    commands = [
        "echo 'hello world'",
        "uptime",
        "",  # empty lines should be skipped
        "who",
    ]
    cmd_file = tempfile.mktemp()
    with open(cmd_file, "w") as opencmds:
        opencmds.write("\n".join(commands))

    class FakeSettings(object):
        command = "somehost"
        command_file = [cmd_file]
        servers = []

    commands_post, settings = get_commands(FakeSettings())

    commands.pop(2)  # remove the empty line
    assert commands == commands_post


def test_cmdfile_ioerrors_exit():
    """If we are unable to read the cmd file, it should SystemExit."""

    fake_file = "/not/even/close/to/real/i/hope"

    class FakeSettings(object):
        command = "somehost"
        command_file = [fake_file]
        servers = []

    with pytest.raises(SystemExit) as error:
        get_commands(FakeSettings())

    assert fake_file in error.exconly()


def test_reading_hostsfile():
    """We should be able to pass in a file with a list of hostnames."""

    hosts = [
        "server-01",
        "server-02",
        "server-03",
        "server-04",
    ]
    hostsfile = tempfile.mktemp()
    with open(hostsfile, "w") as openhosts:
        openhosts.write("\n".join(hosts))

    class FakeSettings(object):
        host_file = [hostsfile]
        servers = []

    settings = FakeSettings()
    get_servers(settings)

    assert hosts == settings.servers


def test_hostsfile_ioerrors_exit():
    """It should SystemExit if we are unable to read the hosts file."""

    fake_file = "/not/even/close/to/real/i/hope"

    class FakeSettings(object):
        host_file = [fake_file]
        servers = []

    with pytest.raises(SystemExit) as error:
        get_servers(FakeSettings())

    assert fake_file in error.exconly()


def test_unlisting_argparse():
    """Ensure we clean up the settings namespace correctly."""

    class FakeSettings(object):
        printFixed = True
        cmd_timeout = [8]
        timeout = [60]
        delay = [10]
        password = ["hunter7"]
        second_password = ["hunter8"]
        jump_pass = ["hunter9"]
        csv_char = [".fail"]  # only the first char should be used
        ascii = True
        threads = [50]
        jump_port = [24]
        port = [25]
        debug = [3]
        output_file = False
        style = None
        width = False

    settings = argparse_unlisted(FakeSettings())

    # things that should just be unlisted if a single element
    unlistings = [
        "cmd_timeout",
        "timeout",
        "delay",
        "password",
        "second_password",
        "jump_pass",
        "port",
        "jump_port",
        "threads",
        "debug",
    ]
    for unlist in unlistings:
        assert getattr(settings, unlist) == getattr(FakeSettings, unlist)[0]

    assert settings.printFixed == 80, "fixed should be 80"
    assert settings.style == 1, "ascii should set style to 1"
    assert settings.csv_char == ".", "csv_char is a single char"


def test_get_password():
    """Ensure we're prompting the user with getpass."""

    class FakeSettings(object):
        usePassword = True
        password = []
        setsecond_password = False
        second_password = []
        setjumpbox_password = False
        jump_host = []
        jump_pass = []

    with patch.object(getpass, "getpass", return_value="mock") as patched:
        settings = get_passwords(FakeSettings())

    patched.assert_called_once_with("Password: ")
    for config in ["password", "second_password", "jump_pass"]:
        assert getattr(settings, config) == "mock", "password should be 'mock'"


def test_get_second_password():
    """Ensure the second password is also prompted for."""

    class FakeSettings(object):
        usePassword = True
        password = "hunter7"
        setsecond_password = True
        second_password = []
        setjumpbox_password = False
        jump_host = []
        jump_pass = []

    with patch.object(getpass, "getpass", return_value="mock") as patched:
        settings = get_passwords(FakeSettings())

    patched.assert_called_once_with("Second password: ")
    assert settings.second_password == "mock"
    assert settings.password == "hunter7"
    assert settings.jump_pass == "hunter7"


def test_get_jump_password():
    """Ensure the jumpbox password is prompted for."""

    class FakeSettings(object):
        usePassword = True
        password = "hunter7"
        setsecond_password = False
        second_password = "hunter8"
        setjumpbox_password = True
        jump_host = ["somehost"]
        jump_pass = []

    with patch.object(getpass, "getpass", return_value="mock") as patched:
        settings = get_passwords(FakeSettings())

    patched.assert_called_once_with("Jumpbox password: ")
    assert settings.jump_pass == "mock"
    assert settings.password == "hunter7"
    assert settings.second_password == "hunter8"


def test_touching_output_file():
    """Check that the output file is writable before starting."""

    class FakeSettings(object):
        output_file = tempfile.mktemp()

    settings = FakeSettings()
    assert not os.path.exists(settings.output_file)
    setup_output_file(settings)
    assert os.path.exists(settings.output_file)


def test_output_file_failure():
    """If we can't write the output file, it should raise SystemExit."""

    class FakeSettings(object):
        output_file = "/this/file/path/probably/doesnt/exist/i/hope"

    with pytest.raises(SystemExit) as error:
        setup_output_file(FakeSettings())

    assert "Could not open output file: " in error.exconly()


def test_fixed_takes_priority():
    """if both --fixed and --width are used, fixed should be prefered."""

    sys.argv.extend(["--settings", "--fixed", "-nNw", "123", "hi", "fake"])
    with pytest.raises(SystemExit) as error:
        cmdline_entry()

    assert "'width': 80" in error.exconly()


def test_stacked_is_called_when_flat():
    """If --flat is used the print_stacked function should be called."""

    sys.argv.extend(["--flat", "hi", "fake"])
    with patch.object(cmdline, "stacked_results") as stack_patch:
        with pytest.raises(SystemExit):
            cmdline_exit(["fake"], {"stacked": True})

    stack_patch.assert_called_once_with(["fake"], {"stacked": True})
