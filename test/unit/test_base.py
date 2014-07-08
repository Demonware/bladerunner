"""Tests for the core Bladerunner behavior."""


import os
import sys
import pytest
import pexpect
import tempfile
from mock import call
from mock import Mock
from mock import patch

from bladerunner import base
from bladerunner import Bladerunner
from bladerunner import ProgressBar
from bladerunner.formatting import FakeStdOut


class TempFile(object):
    """Provides the key file name."""

    @staticmethod
    def get_name():
        if not hasattr(TempFile, "_name"):
            TempFile._name = tempfile.mktemp()
        return TempFile._name


@pytest.fixture
def unicode_chr():
    """Return a consistant unichr/chr accross py2/3."""

    if sys.version_info > (3,):
        return chr
    else:
        return unichr


@pytest.fixture(params=(pexpect.EOF, pexpect.TIMEOUT), ids=("EOF", "TIMEOUT"))
def pexpect_exceptions(request):
    """Parametrizes the EOF and TIMEOUT exceptions thrown by pexpect."""

    return request.param


@pytest.fixture
def fake_key(request):
    """Fixture to provide a fake ssh key file. Adds a finalizer to remove."""

    fakekey = TempFile.get_name()
    with open(fakekey, "w") as key_file:
        key_file.write("ssh-rsa abcdefghijklmnopqrstuvwxyz1234567890 bob@fake")
    request.addfinalizer(key_cleanup)
    return fakekey


def key_cleanup():
    """Removes the test key."""

    os.remove(TempFile.get_name())


def bytes_or_string(string):
    """Converts a string to bytes if we're using python3."""

    if sys.version_info > (3,):
        return bytes(string, "latin-1")
    else:
        return string


def test_run_no_options():
    """Uses Mock to enforce the Bladerunner.run logic with no configuration."""

    runner = Bladerunner()

    with patch.object(runner, "_run_parallel") as patched_run:
        runner.run("nothing", "nowhere")

    patched_run.assert_called_once_with(["nowhere"])


def test_serial_execution():
    """If the delay optios is set, we should call _run_serial."""

    runner = Bladerunner({"delay": 10})

    with patch.object(runner, "_run_serial") as patched_run:
        runner.run("nothing", "nowhere")

    patched_run.assert_called_once_with(["nowhere"])


def test_progressbar_setup():
    """If the progressbar is used it should be of len servers."""

    runner = Bladerunner({"progressbar": True})

    with patch.object(base, "ProgressBar") as patched_pbar:
        with patch.object(runner, "_run_parallel") as patched_run:
            runner.run("nothing", "nowhere")

    patched_pbar.assert_called_once_with(1, runner.options)
    patched_run.assert_called_once_with(["nowhere"])


def test_jumpbox_user_priority():
    """Ensure the jump_user is used over username for the jump host."""

    runner = Bladerunner({
        "username": "joebob",
        "jump_user": "somedude",
        "jump_host": "some_fake_host",
        "jump_pass": "hunter8",
        "jump_port": 2222,
    })

    with patch.object(runner, "connect", return_value=("ok", 0)) as p_connect:
        with patch.object(runner, "_run_serial") as p_run:
            with patch.object(runner, "close") as p_close:
                runner.run("nothing", "nowhere")

    p_connect.assert_called_once_with(
        "some_fake_host",
        "somedude",
        "hunter8",
        2222,
    )
    p_run.assert_called_once_with(["nowhere"])
    p_close.assert_called_once_with("ok", True)


def test_jumpbox_errors_raise():
    """Any error connecting to the jumpbox should bail the job."""

    runner = Bladerunner({
        "jump_host": "some_fake_host",
        "username": "someguy",
        "jump_pass": "hunter7",
        "jump_port": 222,
    })

    with patch.object(runner, "connect", return_value=(None, -1)) as p_connect:
        with pytest.raises(SystemExit) as p_sysexit:
            runner.run("nothing", "nowhere")

    err_msg = p_sysexit.exconly()

    p_connect.assert_called_once_with(
        "some_fake_host",
        "someguy",
        "hunter7",
        222,
    )
    assert runner.errors[0] in err_msg and "Jumpbox Error:" in err_msg


def test_run_thread():
    """If run thread is used the callback should be called with results."""

    runner = Bladerunner()
    callback = Mock()

    with patch.object(runner, "run", return_value="fake") as patched_run:
        runner._run_thread(["nothing"], ["nowhere"], {}, callback)

    patched_run.assert_called_once_with(["nothing"], ["nowhere"], {})
    callback.assert_called_once_with("fake")


def test_run_threaded():
    """Ensure run threaded returns a started threading.Thread."""

    runner = Bladerunner()
    mock_thread = Mock()
    threading_patch = patch.object(
        base.threading,
        "Thread",
        return_value=mock_thread,
    )

    with threading_patch as patched_thread:
        runner.run_threaded(["nothing"], ["nowhere"], {})

    patched_thread.assert_called_once_with(
        target=runner._run_thread,
        args=(["nothing"], ["nowhere"], {}, None),
    )
    assert mock_thread.start.called


@pytest.mark.parametrize(
    "cmds, srvs, cmds_on_svrs, ex_cmds, ex_on_svrs, ex_ret",
    [
        (["fake"], ["somehost"], None, ["fake"], None, ["somehost"]),
        ([], [], {"host": "fake"}, None, {"host": ["fake"]}, ["host"]),
        (
            ["fake"],
            ["10.11.12.0/30"],
            None,
            ["fake"],
            None,
            ["10.11.12.1", "10.11.12.2"],
        ),
        (
            [],
            [],
            {"10.10.10.0/30": "fake"},
            None,
            {"10.10.10.1": ["fake"], "10.10.10.2": ["fake"]},
            ["10.10.10.1", "10.10.10.2"],
        ),
    ],
    ids=("basic", "one cmd_on_server", "network expansion", "cmds on network"),
)
def test_prep_servers(cmds, srvs, cmds_on_svrs, ex_cmds, ex_on_svrs, ex_ret):
    """Prep servers should convert commands_on_servers or network addresses."""

    runner = Bladerunner()
    returned = runner._prep_servers(cmds, srvs, cmds_on_svrs)

    assert runner.commands == ex_cmds
    assert runner.commands_on_servers == ex_on_svrs

    for expected_return in ex_ret:
        assert expected_return in returned
    for ret in returned:
        assert ret in ex_ret


def test_run_parallel():
    """Ensure we call to run parallel safely when the option is set."""

    runner = Bladerunner()

    # the safety should be off by default from library -- cmdline sets it
    assert runner.options["password_safety"] is False

    with patch.object(runner, "_run_parallel_no_check") as patched_no_check:
        runner._run_parallel(["nowhere"])
    patched_no_check.assert_called_once_with(["nowhere"])

    runner.options["password_safety"] = True
    with patch.object(runner, "_run_parallel_safely") as patched_safety:
        runner._run_parallel(["nowhere"])
    patched_safety.assert_called_once_with(["nowhere"])


def test_run_parallel_no_check():
    """Check that we're using concurrent.futures correctly."""

    runner = Bladerunner({"threads": 21})
    map_patch = patch.object(
        base.ThreadPoolExecutor,
        "map",
        return_value=iter(["wat", "ok"])
    )

    with patch.object(base, "ThreadPoolExecutor") as patched_pool:
        runner._run_parallel_no_check(["nowhere"])
    patched_pool.assert_called_once_with(max_workers=21)

    with map_patch as patched_map:
        results = runner._run_parallel_no_check(["nowhere"])
    patched_map.assert_called_once_with(runner._run_single, ["nowhere"])
    assert results == ["wat", "ok"]


def test_run_safely_to_serial():
    """Ensure we only carry on with parallel no check on good first login."""

    runner = Bladerunner({
        "username": "dudebro",
        "password": "hunter99",
        "port": 202,
    })

    with patch.object(runner, "connect", return_value=(None, -2)) as p_connect:
        with patch.object(runner, "_run_serial", return_value=[]) as p_run:
            ret = runner._run_parallel_safely(["one", "two", "three"])

    p_connect.assert_called_once_with(
        "one",
        "dudebro",
        "hunter99",
        202,
    )
    p_run.assert_called_once_with(["two", "three"])
    assert ret == [{"name": "one", "results": [("login", runner.errors[1])]}]


def test_run_safely_to_parralel():
    """Ensure after the first success the rest are run in parallel."""

    runner = Bladerunner({
        "username": "broguy",
        "password": "hunter14",
        "progressbar": True,
        "port": 2244,
    })

    # we have to set up the progressbar ourselves here, normally it'd happen in
    # run once we know the len of servers to run on.
    runner.progress = ProgressBar(3, runner.options)

    with patch.object(runner, "connect", return_value=("ok", 0)) as p_connect:
        with patch.object(runner, "send_commands", return_value=[]) as p_send:
            with patch.object(runner, "close") as p_close:
                with patch.object(runner, "_run_parallel_no_check") as p_run:
                    with patch.object(runner.progress, "update") as p_update:
                        runner._run_parallel_safely(["1st", "2nd", "3rd"])

    p_connect.assert_called_once_with(
        "1st",
        "broguy",
        "hunter14",
        2244,
    )
    p_send.assert_called_once_with("ok", "1st")
    p_close.assert_called_once_with("ok", True)
    # if the progressbar is used we should update it once for the check run
    assert p_update.called
    p_run.assert_called_once_with(["2nd", "3rd"])


def test_run_serial():
    """Ensure we are insertting time delays and running serial correctly."""

    runner = Bladerunner({"delay": 30})

    with patch.object(base.time, "sleep") as p_sleep:
        with patch.object(runner, "_run_single", return_value=[]) as p_run:
            ret = runner._run_serial(["one", "two", "three", "four"])

    assert ret == [[], [], [], []]
    assert p_sleep.call_count == 3
    assert p_run.mock_calls == [
        call("one"),
        call("two"),
        call("three"),
        call("four"),
    ]


def test_run_single_error():
    """Ensure an error is passed back during run_single on connect errors."""

    runner = Bladerunner({
        "username": "dudeguy",
        "password": "hunter111",
        "progressbar": True,
        "port": 2212,
    })

    runner.progress = ProgressBar(1, runner.options)

    with patch.object(runner, "connect", return_value=(None, -3)) as p_connect:
        with patch.object(runner.progress, "update") as p_update:
            ret = runner._run_single("nowhere")

    p_connect.assert_called_once_with(
        "nowhere",
        "dudeguy",
        "hunter111",
        2212,
    )

    # if the progressbar should tick regardless of success
    assert p_update.called
    assert ret == {"name": "nowhere", "results": [("login", runner.errors[2])]}


def test_run_single_success():
    """Ensure the calls to send commands on a single host."""

    runner = Bladerunner({
        "username": "dudeguybro",
        "password": "hunter40",
        "progressbar": True,
        "port": 2012,
    })

    runner.progress = ProgressBar(1, runner.options)

    with patch.object(runner, "connect", return_value=("ok", 0)) as p_connect:
        with patch.object(runner, "send_commands", return_value=[]) as p_send:
            with patch.object(runner, "close") as p_close:
                with patch.object(runner.progress, "update") as p_update:
                    runner._run_single("nowhere")

    p_connect.assert_called_once_with(
        "nowhere",
        "dudeguybro",
        "hunter40",
        2012,
    )
    p_send.assert_called_once_with("ok", "nowhere")
    p_close.assert_called_once_with("ok", True)
    # if the progressbar is used we should tick it once for the check run
    assert p_update.called


def test_send_cmd_unix_endings(unicode_chr):
    """Ensure the correct line ending is used when unix is specified."""

    runner = Bladerunner({
        "unix_line_endings": True,
        "windows_line_endings": False,
        "second_password": "hunter55",
    })
    server = Mock()
    # server.expect returns an integer of the prompt matched in its list
    # we want to return N+1 to simulate matching a passwd prompt
    server.expect = Mock(return_value=(
        len(runner.options["shell_prompts"]) +
        len(runner.options["extra_prompts"]) +
        1
    ))

    with patch.object(base, "format_output") as p_format_output:
        runner._send_cmd("fake", server)

    p_format_output.assert_called_once_with(server.before, "fake")
    server.send.assert_called_once_with("fake{0}".format(unicode_chr(0x000A)))

    # the second password should be send with sendline
    server.sendline.assert_called_once_with("hunter55")

    assert server.expect.call_count == 2


def test_send_cmd_winderps_endings(unicode_chr):
    """Ensure the wrong line endings are used when winderps is required."""

    runner = Bladerunner({
        "unix_line_endings": False,
        "windows_line_endings": True,
    })
    server = Mock()
    server.expect = Mock(return_value=1)

    with patch.object(base, "format_output") as p_format_output:
        runner._send_cmd("faked", server)

    p_format_output.assert_called_once_with(server.before, "faked")
    server.send.assert_called_once_with("faked{0}{1}".format(
        unicode_chr(0x000D),
        unicode_chr(0x000A),
    ))

    assert server.expect.call_count == 1


@pytest.mark.skipif(
    hasattr(os, "uname") and "darwin" in os.uname()[0].lower(),
    reason="macs prefer unix line endings",
)
def test_send_cmd_no_preference():
    """Ensure we call to pexpect's sendline which uses os.linesep."""

    runner = Bladerunner()
    server = Mock()
    server.expect = Mock(return_value=1)

    with patch.object(base, "format_output") as p_format_output:
        runner._send_cmd("mock", server)

    p_format_output.assert_called_once_with(server.before, "mock")
    server.sendline.assert_called_once_with("mock")

    assert server.expect.call_count == 1


def test_fallback_prompt_guess(pexpect_exceptions):
    """If a TIMEOUT or EOF error is raised, call _try_for_unmatched_prompt."""

    server = Mock()
    server.expect = Mock(side_effect=pexpect_exceptions("mock exception"))
    runner = Bladerunner({
        "username": "guy",
        "password": "hunter2",
    })

    with patch.object(runner, "_try_for_unmatched_prompt") as p_try_for:
        runner._send_cmd("not real", server)

    p_try_for.assert_called_once_with(server, server.before, "not real")


@pytest.mark.skipif(
    hasattr(os, "uname") is False or "darwin" not in os.uname()[0].lower(),
    reason="only for macs",
)
def test_apple_uses_unix_endings():
    """If not specified darwin kernels should use unix line endings."""

    runner = Bladerunner()
    assert runner.options["unix_line_endings"]
    assert not runner.options["windows_line_endings"]


def test_try_for_unmatched_works():
    """Ensure logic when the first attempt at guessing works."""

    runner = Bladerunner()

    server = Mock()
    with patch.object(runner, "_push_expect_forward") as p_push:
        with patch.object(base, "format_output") as p_format:
            runner._try_for_unmatched_prompt(
                server,
                bytes_or_string("fake output"),
                "fake",
            )

    assert "fake\\ output" in runner.options["shell_prompts"]
    p_format.assert_called_once_with(bytes_or_string("fake output"), "fake")
    p_push.assert_called_once_with(server)


def test_try_for_unmatched_fails():
    """Bladerunner "hits enter" up to 3 times to try to guess the prompt."""

    runner = Bladerunner()
    server = Mock()
    server.expect = Mock(side_effect=pexpect.TIMEOUT("fake"))
    server.before = bytes_or_string("mock output")

    with patch.object(runner, "send_interrupt") as p_interrupt:
        ret = runner._try_for_unmatched_prompt(
            server,
            bytes_or_string("out"),
            "fake",
        )

    assert ret == -1
    assert "out" in runner.options["shell_prompts"]
    p_interrupt.assert_called_once_with(server)


def test_try_unmatched_works_from_login():
    """When guessing prompt on login, return the server object and status."""

    runner = Bladerunner()
    server = Mock()
    with patch.object(runner, "_push_expect_forward") as p_push:
        ret = runner._try_for_unmatched_prompt(
            server,
            bytes_or_string("out"),
            "fake",
            True,
        )

    p_push.assert_called_once_with(server)
    assert ret == (server, 1)


def test_try_unmatched_fails_from_login():
    """When trying to guess on login, return None, -6 on error."""

    runner = Bladerunner()
    server = Mock()
    server.expect = Mock(side_effect=pexpect.TIMEOUT("fake"))
    server.before = bytes_or_string("mock output")

    with patch.object(runner, "send_interrupt") as p_interrupt:
        ret = runner._try_for_unmatched_prompt(
            server,
            bytes_or_string("out"),
            "fake",
            True,
        )

    assert ret == (None, -6)
    assert "out" in runner.options["shell_prompts"]
    p_interrupt.assert_called_once_with(server)


def test_send_commands_basic():
    """Simple test case of sending commands on a pexpect object."""

    runner = Bladerunner()
    runner.commands = ["fake"]
    server = Mock()
    with patch.object(runner, "_send_cmd", return_value="ok") as p_send_cmd:
        ret = runner.send_commands(server, "nowhere")

    p_send_cmd.assert_called_once_with("fake", server)
    assert ret == {"name": "nowhere", "results": [("fake", "ok")]}


def test_send_commands_on_hosts():
    """Testing the calls when using the commands on servers dictionary."""

    runner = Bladerunner()
    runner.commands_on_servers = {"nowhere": ["mocked"]}
    server = Mock()

    with patch.object(runner, "_send_cmd", return_value=-1) as p_send_cmd:
        ret = runner.send_commands(server, "nowhere")

    p_send_cmd.assert_called_once_with("mocked", server)
    assert ret == {"name": "nowhere", "results": [
        ("mocked", "did not return after issuing: mocked")]}


def test_send_commands_no_output():
    """Test the calls when a command sent has no output."""

    runner = Bladerunner({"debug": -1})
    runner.commands = ["fake"]
    server = Mock()
    with patch.object(runner, "_send_cmd", return_value="") as p_send_cmd:
        ret = runner.send_commands(server, "nowhere")

    p_send_cmd.assert_called_once_with("fake", server)
    assert ret == {"name": "nowhere", "results": [
        ("fake", "no output from: fake")]}


def test_build_ssh_commands():
    """Ensure we are building the ssh connect command correctly."""

    runner = Bladerunner({"debug": -1})  # should be invalid/ignored
    cmd = runner._build_ssh_command("nowhere", "joe", 44)
    assert cmd == "ssh -p 44 -t joe@nowhere"


def test_build_ssh_with_key(fake_key):
    """Ensure the fake ssh key (fixture) is used with -i in the ssh cmd."""

    runner = Bladerunner({"ssh_key": fake_key, "debug": 3})
    cmd = runner._build_ssh_command("somewhere", "bob", 66)
    assert cmd == "ssh -p 66 -t -i {0} -vvv bob@somewhere".format(fake_key)


def test_connect_no_resolve():
    """If we can't resolve the host connect should return immediately."""

    runner = Bladerunner()
    with patch.object(base, "can_resolve", return_value=False):
        assert runner.connect("nowhere", "bob", "hunter2", 22) == (None, -3)


def test_connect_new_connection():
    """Ensure Bladerunner creates the initial pexpect object correctly."""

    runner = Bladerunner({"debug": 2, "jump_host": "nowhere"})
    sshr = Mock()
    sshr.expect = Mock(return_value="faked")

    with patch.object(base, "can_resolve", return_value=True):
        with patch.object(base.pexpect, "spawn", return_value=sshr) as p_spawn:
            with patch.object(runner, "_multipass") as p_multipass:
                runner.connect("nowhere", "bobby", "hunter44", 15)

    p_spawn.assert_called_once_with("ssh -p 15 -t -vv bobby@nowhere")
    p_multipass.assert_called_once_with(sshr, "hunter44", "faked")
    sshr.expect.assert_called_once_with(
        runner.options["passwd_prompts"] +
        runner.options["shell_prompts"] +
        runner.options["extra_prompts"],
        runner.options["timeout"],
    )
    assert runner.sshc == sshr  # could be used as a jumpbox in future connects
    assert sshr.logfile_read == FakeStdOut  # debug is set, logging to stdout


def test_connect_new_exceptions(pexpect_exceptions):
    """If TIMEOUT or EOF exceptions are raised, connect returns (None, -1)."""

    runner = Bladerunner({"debug": 2, "jump_host": "nowhere"})
    sshr = Mock()
    sshr.expect = Mock(side_effect=pexpect_exceptions("faked"))

    with patch.object(base, "can_resolve", return_value=True):
        with patch.object(base.pexpect, "spawn", return_value=sshr) as p_spawn:
            res = runner.connect("nowhere", "noone", "hunter29", 99)

    p_spawn.assert_called_once_with("ssh -p 99 -t -vv noone@nowhere")
    assert res == (None, -1)


def test_connect_from_jumpbox():
    """Test the calls through connect for a succesful login from a jumpbox."""

    runner = Bladerunner({"jump_host": "faked"})
    runner.sshc = Mock()
    runner.sshc.before.find = Mock(return_value=-1)  # permission not denied
    runner.sshc.expect = Mock(return_value="fake")

    with patch.object(base, "can_resolve", return_value=True):
        with patch.object(runner, "_multipass") as p_multipass:
            runner.connect("where", "johnny", "hunter13", 43)

    runner.sshc.sendline.assert_called_once_with("ssh -p 43 -t johnny@where")
    runner.sshc.expect.assert_called_once_with(
        runner.options["passwd_prompts"] +
        runner.options["shell_prompts"] +
        runner.options["extra_prompts"],
        runner.options["timeout"],
    )
    p_multipass.assert_called_once_with(runner.sshc, "hunter13", "fake")


def test_connect_from_jb_failures(pexpect_exceptions):
    """Test the pexpect excpetions are caught from inside a jumpbox."""

    runner = Bladerunner({"jump_host": "notreal"})
    runner.sshc = Mock()
    runner.sshc.expect = Mock(side_effect=pexpect_exceptions("fake error"))

    with patch.object(base, "can_resolve", return_value=True):
        with patch.object(runner, "send_interrupt") as p_interrupt:
            ret = runner.connect("place", "frank", "hunter63", 101)

    runner.sshc.sendline.assert_called_once_with("ssh -p 101 -t frank@place")
    p_interrupt.assert_called_once_with(runner.sshc)
    assert ret == (None, -1)


def test_connect_from_jb_denied():
    """Ensure we look through the before text for 'Permission denied's."""

    runner = Bladerunner({"jump_host": "mocked"})
    runner.sshc = Mock()
    runner.sshc.before.find = Mock(return_value=1)

    with patch.object(base, "can_resolve", return_value=True):
        with patch.object(runner, "send_interrupt") as p_interrupt:
            ret = runner.connect("home", "self", "hunter22", 443)

    runner.sshc.before.find.assert_called_once_with("Permission denied")
    runner.sshc.sendline.assert_called_once_with("ssh -p 443 -t self@home")
    runner.sshc.expect.assert_called_once_with(
        runner.options["passwd_prompts"] +
        runner.options["shell_prompts"] +
        runner.options["extra_prompts"],
        runner.options["timeout"],
    )
    p_interrupt.assert_called_once_with(runner.sshc)
    assert ret == (None, -4)


def test_multipass():
    """Ensure the correct calls are made to attempt multiple passwords."""

    runner = Bladerunner()
    sshc = Mock()
    with patch.object(runner, "login", return_value=("fake", 1)) as p_login:
        assert runner._multipass(sshc, "hunter11", 123) == ("fake", 1)

    p_login.assert_called_once_with(sshc, "hunter11", 123)


def test_multipass_failure():
    """Ensure all passwords are tried before returning failure."""

    runner = Bladerunner()
    sshc = Mock()
    with patch.object(runner, "login", return_value=("fake", -4)) as p_login:
        ret = runner._multipass(sshc, ["hunter1", "hunter2"], 12)

    assert p_login.mock_calls == [
        call(sshc, "hunter1", 12),
        call(sshc, "hunter2", 12),
    ]
    assert ret == (None, -4)


def test_login_new_host():
    """The first passwd prompt is a match for a new ssh key identity."""

    runner = Bladerunner()
    sshc = Mock()
    sshc.expect = Mock(side_effect=iter([2, 22]))  # passwd, then shell
    assert runner.login(sshc, "fake", 0) == (sshc, 1)
    assert sshc.sendline.mock_calls == [call("yes"), call("fake")]


def test_login_new_host_failures(pexpect_exceptions):
    """Catch the pexpect EOF and TIMEOUT exceptions after accepting the key."""

    runner = Bladerunner()
    sshc = Mock()
    sshc.expect = Mock(side_effect=pexpect_exceptions("fake exception"))

    with patch.object(runner, "send_interrupt") as p_interrupt:
        assert runner.login(sshc, "hunter12", 0) == (None, -1)

    sshc.sendline.assert_called_once_with("yes")
    p_interrupt.assert_called_once_with(sshc)


def test_login_send_password():
    """Ensure then calls when logging in properly with a passwd prompt."""

    runner = Bladerunner()
    sshc = Mock()
    sshc.expect = Mock(return_value=22)
    assert runner.login(sshc, "mock word", 1) == (sshc, 1)
    sshc.sendline.assert_called_once_with("mock word")


def test_login_fail_guess(pexpect_exceptions):
    """When sending a password fails try to guess the shell prompt."""

    runner = Bladerunner()
    sshc = Mock()
    sshc.expect = Mock(side_effect=pexpect_exceptions("fake explosion"))

    with patch.object(runner, "_try_for_unmatched_prompt") as p_try_for:
        runner.login(sshc, "passwerd", 1)

    sshc.sendline.assert_called_once_with("passwerd")
    p_try_for.assert_called_once_with(
        sshc,
        sshc.before,
        "login",
        _from_login=True,
    )


def test_login_passwd_fail():
    """Ensure the calls when receiving another passwd prompt after sending."""

    runner = Bladerunner()
    sshc = Mock()
    sshc.expect = Mock(return_value=1)

    with patch.object(runner, "send_interrupt") as p_interrupt:
        assert runner.login(sshc, "fakepasswd", 1) == (sshc, -5)

    sshc.sendline.assert_called_once_with("fakepasswd")
    p_interrupt.assert_called_once_with(sshc)


def test_login_unexpected_prompt():
    """We received a password prompt when no password is in use."""

    runner = Bladerunner()
    sshc = Mock()

    with patch.object(runner, "send_interrupt") as p_interrupt:
        assert runner.login(sshc, None, 1) == (None, -2)

    p_interrupt.assert_called_once_with(sshc)


def test_login_unused_password():
    """We logged in but did not send a password (unexpected key auth)."""

    runner = Bladerunner()
    sshc = Mock()
    assert runner.login(sshc, "no passwd sent", 9000) == (sshc, 1)


def test_send_interrupt(unicode_chr, pexpect_exceptions):
    """Ensure Bladerunner sends ^c to the sshc when jumpboxing."""

    runner = Bladerunner()
    sshc = Mock()
    # any EOF or TIMEOUT exceptions are ignored
    sshc.expect = Mock(side_effect=pexpect_exceptions("faked exception"))

    with patch.object(runner, "_push_expect_forward") as p_push:
        runner.send_interrupt(sshc)

    sshc.sendline.assert_called_once_with(unicode_chr(0x003))
    sshc.expect.assert_called_once_with(
        runner.options["shell_prompts"] + runner.options["extra_prompts"], 3)
    p_push.assert_called_once_with(sshc)


def test_push_expect_forward(pexpect_exceptions):
    """Verify the calls made to push the pexpect connection object forward."""

    runr = Bladerunner()
    sshc = Mock()
    # any EOF or TIMEOUT exceptions are ignored
    sshc.expect = Mock(side_effect=pexpect_exceptions("faked exception"))

    runr._push_expect_forward(sshc)

    assert sshc.expect.mock_calls == [
        call(runr.options["shell_prompts"] + runr.options["extra_prompts"], 2),
        call(runr.options["shell_prompts"] + runr.options["extra_prompts"], 2),
    ]


def test_close_and_terminate():
    """Sends 'exit' and terminates the pexpect connection object."""

    runner = Bladerunner()
    sshc = Mock()
    runner.close(sshc, True)
    sshc.sendline.assert_called_once_with("exit")
    assert sshc.terminate.called


def test_close_keep_open(pexpect_exceptions):
    """Ensure we can close a connection inside another, for jumpboxes."""

    runner = Bladerunner()
    sshc = Mock()
    # exceptions are ignored here, we hope we're back on the jumpbox
    sshc.expect = Mock(side_effect=pexpect_exceptions("mock exception"))

    runner.close(sshc, False)
    sshc.sendline.assert_called_once_with("exit")
    sshc.expect.assert_called_once_with(
        runner.options["shell_prompts"] +
        runner.options["extra_prompts"],
        runner.options["cmd_timeout"],
    )


def test_one_extra_prompt():
    """You can use a string or a list to provide extra prompts."""

    runner = Bladerunner({"extra_prompts": "single_element"})
    assert "single_element" in runner.options["extra_prompts"]
