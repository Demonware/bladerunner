"""Tests for the command line entry."""


import os
import sys
import getpass
import tempfile
import unittest
from mock import Mock, patch

if sys.version_info <= (2, 7):
    import unittest2 as unittest
else:
    import unittest

if sys.version_info >= (3, 0):
    from io import StringIO
else:
    from StringIO import StringIO

from bladerunner import cmdline
from bladerunner.base import Bladerunner
from bladerunner.cmdline import (
    argparse_unlisted,
    cmdline_entry,
    cmdline_exit,
    get_commands,
    get_passwords,
    get_servers,
    print_help,
    setup_output_file,
)


class CmdLineTests(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        self.py3_enabled = sys.version_info > (3,)
        # some command line flags don't perfectly line up to br options
        self.option_mismatches = {
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
        super(CmdLineTests, self).__init__(*args, **kwargs)

    def setUp(self):
        """Save sys.argv, stdout/err..."""

        self._argv = sys.argv
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.argv = ["bladerunner"]
        sys.stdout = StringIO()
        sys.stderr = StringIO()

    def tearDown(self):
        """Restore sys.argv, stdout/err..."""

        sys.argv = self._argv
        sys.stdout = self._stdout
        sys.stderr = self._stderr

    def _get_error_message(self, error):
        """Return the error message from a caught exception.

        Usage example:

        def do_the_exit():
            raise SystemExit("time to leave")

        class TestThings(BladerunnerTest):
            def test_exit(self):
                with self.assertRaises(SystemExit) as error:
                    do_the_exit()

                message = self._get_error_message(error)
                self.assertEqual("time to leave", error)
        """

        if self.py3_enabled:
            message = str(error.exception.code).strip()
        else:
            message = str(error.exception.message).strip()

        message += sys.stdout.getvalue().strip()
        message += sys.stderr.getvalue().strip()

        return message

    def test_get_help(self):
        """Ensure we raise SystemExit with a help message."""

        sys.argv.append("--help")
        helper = Mock(spec=print_help)
        dummy_runner = Bladerunner()
        with self.assertRaises(SystemExit) as error:
            cmdline_entry()
            self.assertTrue(helper.called)

        message = self._get_error_message(error)

        for option in dummy_runner.options:
            if option in self.option_mismatches:
                option_key = self.option_mismatches[option]
            else:
                option_key = option

            self.assertIn(option_key.replace("_", "-"), message)

    def test_get_settings(self):
        """You should get a dump of the settings if you use --settings."""

        sys.argv.extend(["--settings", "-Nn", "uptime", "somehost.com"])
        with self.assertRaises(SystemExit) as error:
            cmdline_entry()

        message = self._get_error_message(error)

        should_finds = [
            "command='uptime'",
            "servers=['somehost.com']",
            "debug=False",
            "password_safety=False",
            "password=None",
            "command_file=False",
        ]
        for should_find in should_finds:
            self.assertIn(should_find, message)

    def test_fixed_width_with_csv(self):
        """Should raise a usage error."""

        sys.argv.extend(["--fixed", "--csv", "uptime", "somehost"])
        with self.assertRaises(SystemExit):
            cmdline_entry()

    def test_no_servers_raises(self):
        """Should get an error unless both command and server are supplied."""

        sys.argv.append("uptime")
        with self.assertRaises(SystemExit):
            cmdline_entry()

    def test_ssh_key_passing(self):
        """Ensure we can provide a non-standard ssh key path."""

        sys.argv.extend(["--ssh-key", "/home/bob/ssh_key", "-nN", "w", "host"])
        cmds, servers, options = cmdline_entry()
        self.assertEqual(options["ssh_key"], "/home/bob/ssh_key")
        self.assertEqual(["host"], servers)
        self.assertEqual(["w"], cmds)
        self.assertIsNone(options["username"])

    def test_username_passing(self):
        """Ensure we can use a username that's not our own."""

        sys.argv.extend(["-u", "joebob", "-nN", "w", "host"])
        cmds, servers, options = cmdline_entry()
        self.assertEqual(options["username"], "joebob")
        self.assertEqual(["host"], servers)
        self.assertEqual(["w"], cmds)

    def test_jumpbox_username_passing(self):
        """Ensure we can use a jumpbox username that's not our own."""

        sys.argv.extend(["-U", "joebob", "-nN", "w", "host"])
        cmds, servers, options = cmdline_entry()
        self.assertEqual(options["jump_user"], "joebob")
        self.assertEqual(["host"], servers)
        self.assertEqual(["w"], cmds)
        self.assertIsNone(options["username"])

    def test_debugging(self):
        """Ensure debug with no int sets debug to True."""

        sys.argv.extend(["--debug", "-nN", "w", "host"])
        cmds, servers, options = cmdline_entry()
        self.assertTrue(options["debug"])
        self.assertEqual(["host"], servers)
        self.assertEqual(["w"], cmds)
        self.assertIsNone(options["username"])

    def test_csv_becomes_set_from_char(self):
        """If the csv_char is non-standard, enable csv output."""

        sys.argv.extend(["--csv-separator", "j", "-nN", "w", "host"])
        cmds, servers, options = cmdline_entry()
        self.assertEqual(["host"], servers)
        self.assertEqual(["w"], cmds)
        self.assertEqual(options["style"], -1)
        self.assertEqual(options["csv_char"], "j")

    def test_invalid_style_is_csv(self):
        """If the user supplies an invalid style int, should default to CSV."""

        options = {"style": 1234}
        # <= py2.6 doesn't like multi-with statements
        with self.assertRaises(SystemExit):
            with patch.object(cmdline, "csv_results") as csv:
                cmdline_exit([], options)

        self.assertTrue(csv.called)

    def test_valid_style_is_pretty(self):
        """If style is valid, the output should be parsed by pretty_results."""

        options = {"style": 2}
        with self.assertRaises(SystemExit):
            with patch.object(cmdline, "pretty_results") as pretty:
                cmdline_exit([], options)

        self.assertTrue(pretty.called)

    def test_unicode_errors_revert_csv(self):
        """Fake an output issue to ensure fallback to CSV results."""

        options = {"style": 2}
        results = [{"name": "fake", "results": [("echo wat", "wat")]}]

        if self.py3_enabled:
            second = "unichr"
        else:
            second = unicode("unichr")

        mock_error = Mock(
            side_effect=UnicodeEncodeError("utf-8", second, 1, 1, "chars")
        )

        with self.assertRaises(SystemExit):
            with patch.object(cmdline, "csv_results") as csv:
                with patch.object(cmdline, "pretty_results", new=mock_error):
                    cmdline_exit(results, options)

        self.assertTrue(csv.called)

    def test_reading_command_file(self):
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
        self.assertEqual(commands, commands_post)

    def test_cmdfile_ioerrors_exit(self):
        """If we are unable to read the cmd file, it should SystemExit."""

        fake_file = "/not/even/close/to/real/i/hope"

        class FakeSettings(object):
            command = "somehost"
            command_file = [fake_file]
            servers = []

        with self.assertRaises(SystemExit) as error:
            get_commands(FakeSettings())

        message = self._get_error_message(error)
        self.assertIn(fake_file, message)

    def test_reading_hostsfile(self):
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

        self.assertEqual(hosts, settings.servers)

    def test_hostsfile_ioerrors_exit(self):
        """It should SystemExit if we are unable to read the hosts file."""

        fake_file = "/not/even/close/to/real/i/hope"

        class FakeSettings(object):
            host_file = [fake_file]
            servers = []

        with self.assertRaises(SystemExit) as error:
            get_servers(FakeSettings())

        message = self._get_error_message(error)
        self.assertIn(fake_file, message)

    def test_unlisting_argparse(self):
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
        for unlisting in unlistings:
            self.assertEqual(
                getattr(settings, unlisting),
                getattr(FakeSettings, unlisting)[0],
                "{0} was not unlisted".format(unlisting),
            )

        self.assertEqual(settings.printFixed, 80, "fixed == 80")
        self.assertEqual(settings.style, 1, "ascii should set style to 1")
        self.assertEqual(settings.csv_char, ".", "csv_char is a single char")

    def test_get_password(self):
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
            self.assertEqual(
                getattr(settings, config),
                "mock",
                "password should be 'mock'",
            )

    def test_get_second_password(self):
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
        self.assertEqual(settings.second_password, "mock")
        self.assertEqual(settings.password, "hunter7")
        self.assertEqual(settings.jump_pass, "hunter7")

    def test_get_jump_password(self):
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
        self.assertEqual(settings.jump_pass, "mock")
        self.assertEqual(settings.password, "hunter7")
        self.assertEqual(settings.second_password, "hunter8")

    def test_touching_output_file(self):
        """Check that the output file is writable before starting."""

        class FakeSettings(object):
            output_file = tempfile.mktemp()

        settings = FakeSettings()
        self.assertFalse(os.path.exists(settings.output_file))
        setup_output_file(settings)
        self.assertTrue(os.path.exists(settings.output_file))

    def test_output_file_failure(self):
        """If we can't write the output file, it should raise SystemExit."""

        class FakeSettings(object):
            output_file = "/this/file/path/probably/doesnt/exist/i/hope"

        with self.assertRaises(SystemExit) as error:
            setup_output_file(FakeSettings())

        message = self._get_error_message(error)
        self.assertIn("Could not open output file: ", message)


if __name__ == "__main__":
    unittest.main()
