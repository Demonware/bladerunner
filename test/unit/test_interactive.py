"""Unit tests for BladerunnerInteractive objects."""


import mock
import pytest

from bladerunner import interactive
from bladerunner.base import Bladerunner
from bladerunner.interactive import BladerunnerInteractive


def test_object_return():
    """Ensure the object returned from Bladerunner.interactive is correct."""

    runner = Bladerunner()
    inter = runner.interactive("somewhere_fake")
    assert isinstance(inter, BladerunnerInteractive)


def test_connect():
    """Ensure the correct calls are made to the base object to connect."""

    runner = Bladerunner()
    inter = runner.interactive("somewhere_not_real")

    con_mock = mock.patch.object(
        inter.bladerunner,
        "connect",
        return_value=("monkeys", 0),  # fake connecting without error
    )

    with con_mock as mock_connect:
        assert inter.connect(status_return=True) is True

    assert inter.sshr == "monkeys"
    mock_connect.assert_called_once_with(
        "somewhere_not_real",
        runner.options["username"],
        runner.options["password"],
        runner.options["port"],
    )


def test_connect_error():
    """If the connect fails, it should be logged and sshr should stay None."""

    runner = Bladerunner()
    inter = runner.interactive("the_fake_spot")

    con_mock = mock.patch.object(
        inter.bladerunner,
        "connect",
        return_value=("an error", -1),  # fake a connection error return
    )

    log_mock = mock.patch.object(inter, "log")

    with con_mock as mock_connect:
        with log_mock as mock_log:
            assert inter.connect() is None

    mock_connect.assert_called_once_with(
        "the_fake_spot",
        runner.options["username"],
        runner.options["password"],
        runner.options["port"],
    )

    mock_log.assert_called_once_with(runner.errors[0])


def test_connect_jumpbox():
    """Ensure the calls to connect while using a jumpbox."""

    runner = Bladerunner({"jump_host": "not_a_real_thing"})
    inter = runner.interactive("also_not_real")

    con_mock = mock.patch.object(
        inter.bladerunner,
        "connect",
        return_value=("bananas", 0),  # fake connecting without error
    )

    with con_mock as mock_connect:
        inter.connect()

    assert inter.bladerunner.sshc == "bananas"
    assert inter.sshr == "bananas"

    assert mock_connect.call_count == 2
    mock_connect.assert_any_call(
        "not_a_real_thing",
        runner.options["username"],  # a passwd was not set for
        runner.options["password"],  # the jumpbox user so fallback
        runner.options["port"],
    )

    mock_connect.assert_any_call(
        "also_not_real",
        runner.options["username"],
        runner.options["password"],
        runner.options["port"],
    )


def test_connect_jumpbox_error():
    """If the connect to the jumpbox fails, connect should short-circuit."""

    runner = Bladerunner({"jump_host": "nowhere_real"})
    inter = runner.interactive("some_fake_place")

    con_mock = mock.patch.object(
        inter.bladerunner,
        "connect",
        return_value=("bad things", -3),  # fake a connection error return
    )

    log_mock = mock.patch.object(inter, "log")

    with con_mock as mock_connect:
        with log_mock as mock_log:
            assert inter.connect(status_return=True) is False

    mock_connect.assert_called_once_with(
        "nowhere_real",
        runner.options["username"],
        runner.options["password"],
        runner.options["port"],
    )

    mock_log.assert_called_once_with(runner.errors[2])


def test_reconnect():
    """Ensure the interactive object logs and reconnects correctly."""

    runner = Bladerunner()
    inter = runner.interactive("some_place_which_isnt_real")

    with mock.patch.object(inter, "log") as mock_log:
        with mock.patch.object(inter, "end") as mock_end:
            with mock.patch.object(inter, "connect") as mock_connect:
                inter._reconnect()

    mock_log.assert_called_once_with(
        "connection to some_place_which_isnt_real has been lost, reconnecting"
    )

    mock_end.assert_called_once_with()
    mock_connect.assert_called_once_with(status_return=True)


def test_reconnect_interrupt():
    """Ensure the user can cleanly interrupt the interactive reconnect."""

    runner = Bladerunner()
    inter = runner.interactive("nowhere_in_particular")

    # simulate a user pressing ctrl+c by having the connect method raise
    connect_mock = mock.patch.object(
        inter,
        "connect",
        side_effect=KeyboardInterrupt
    )

    with mock.patch.object(inter, "log") as mock_log:
        with mock.patch.object(inter, "end") as mock_end:
            with connect_mock as mock_connect:
                inter._reconnect()

    assert mock_log.call_count == 2
    mock_log.assert_any_call(
        "connection to nowhere_in_particular has been lost, reconnecting"
    )
    mock_log.assert_any_call("cancelled reconnect, ending session")

    # one on the old connection, one after being interrupted
    assert mock_end.call_count == 2

    mock_connect.assert_called_once_with(status_return=True)


def test_end():
    """Ensure the interactive session properly cleans up sessions."""

    runner = Bladerunner()
    inter = runner.interactive("no_place")
    sshr = mock.Mock()
    inter.sshr = sshr

    with mock.patch.object(inter.bladerunner, "close") as mock_close:
        assert inter.end() is None

    mock_close.assert_called_once_with(sshr, True)

    assert inter.sshr is None


def test_end_shortcut():
    """If end is called before connect it should short-circuit."""

    runner = Bladerunner()
    inter = runner.interactive("seriously_no_where")

    assert inter.end() is None
    assert inter.sshr is None


def test_end_jumpbox():
    """Ensure the calls made to close the interactive session with jumpbox."""

    runner = Bladerunner({"jump_host": "some_jumper"})
    inter = runner.interactive("somewhere_beyond_a_wall")
    sshr = mock.Mock()
    sshc = mock.Mock()
    inter.sshr = sshr
    inter.bladerunner.sshc = sshc

    with mock.patch.object(inter.bladerunner, "close") as mock_close:
        assert inter.end() is None

    assert inter.sshr is None

    assert mock_close.call_count == 2
    mock_close.assert_any_call(sshr, False)
    mock_close.assert_any_call(sshc, True)


def test_end_raises():
    """If end encounters an OSError other than errcode 5, it should raise."""

    runner = Bladerunner()
    inter = runner.interactive("some_unreal_location")
    sshr = mock.Mock()
    inter.sshr = sshr

    fake_os_error = OSError()
    fake_os_error.errno = 5

    close_mock = mock.patch.object(
        inter.bladerunner,
        "close",
        side_effect=fake_os_error,
    )

    with close_mock as mock_close:
        assert inter.end() is None

    assert inter.sshr is None

    mock_close.assert_called_once_with(sshr, True)

    # now do it again with an errno that isn't 5
    inter.sshr = sshr
    fake_os_error.errno = 14

    with pytest.raises(OSError):
        with close_mock as mock_close:
            assert inter.end() is None

    assert inter.sshr == sshr
    mock_close.assert_called_once_with(sshr, True)


def test_run():
    """Basic case to ensure the proper calls are made to the base object."""

    runner = Bladerunner()
    inter = runner.interactive("no_real_location")
    sshr = mock.Mock()
    inter.sshr = sshr

    send_mock = mock.patch.object(
        inter.bladerunner,
        "_send_cmd",
        return_value="some fake output",
    )

    with send_mock as mock_send:
        assert inter.run("some fake command") == "some fake output"

    mock_send.assert_called_once_with("some fake command", sshr)


def test_run_init_connect():
    """If run is ran before connect, connect should be called."""

    runner = Bladerunner()
    inter = runner.interactive("unknown_location")
    sshr_mock = mock.Mock()

    def con_se():
        """Pretend like the connect worked and updated the sshr object."""
        inter.sshr = sshr_mock

    send_mock = mock.patch.object(
        inter.bladerunner,
        "_send_cmd",
        return_value=-1,
    )

    with mock.patch.object(inter, "connect", side_effect=con_se) as mock_con:
        with mock.patch.object(inter, "log") as mock_log:
            with send_mock as mock_send:
                assert inter.run("some command") == (
                    "did not return after issuing: some command"
                )

    mock_log.assert_called_once_with(
        "establishing connection to unknown_location"
    )
    mock_con.assert_called_once_with()
    mock_send.assert_called_once_with("some command", sshr_mock)


def test_run_connect_canceled():
    """Ensure the user can cleanly break out of an auto-connect from run."""

    runner = Bladerunner()
    inter = runner.interactive("the_place_which_is_not_real")

    connect_mock = mock.patch.object(
        inter,
        "connect",
        side_effect=KeyboardInterrupt,
    )

    with connect_mock as mock_connect:
        with mock.patch.object(inter, "log") as mock_log:
            with mock.patch.object(inter, "end") as mock_end:
                assert inter.run("doesnt matter") == (
                    "connection to the_place_which_is_not_real was canceled"
                )

    mock_end.assert_called_once_with()
    mock_log.assert_called_once_with(
        "establishing connection to the_place_which_is_not_real"
    )
    mock_connect.assert_called_once_with()


def test_run_on_closed():
    """If the session is closed it will be None. .run() should shortcut."""

    runner = Bladerunner()
    inter = runner.interactive("no_matter")
    inter.sshr = None

    assert inter.run("anything") == "connection to no_matter is closed"


def test_run_raises():
    """Run should re-raise any OSErrors other than errno 5 from _send_cmd.

    On the case that _send_cmd does raise OSError(5); _reconnect should be
    called and if the status_return is True, run should call itself again
    """

    runner = Bladerunner()
    inter = runner.interactive("some_interactive_place")
    # we need to move the run method to a different name so we can test
    # it calling itself recursively with mock
    inter.moved_run = inter.run
    sshr = mock.Mock()
    inter.sshr = sshr

    fake_os_error = OSError()
    fake_os_error.errno = 5

    send_mock = mock.patch.object(
        inter.bladerunner,
        "_send_cmd",
        side_effect=fake_os_error,
    )

    reconnect_mock = mock.patch.object(inter, "_reconnect", return_value=True)

    with send_mock as mock_send:
        with reconnect_mock as mock_reconnect:
            with mock.patch.object(inter, "run") as mock_run:
                inter.moved_run("something important")

    mock_send.assert_called_once_with("something important", sshr)
    mock_reconnect.assert_called_once_with()
    mock_run.assert_called_once_with("something important")

    # now run essentially the same test again but have the reconnect fail
    reconnect_mock = mock.patch.object(inter, "_reconnect", return_value=False)

    with send_mock as mock_send:
        with reconnect_mock as mock_reconnect:
            assert inter.moved_run("something important") == (
                "connection to some_interactive_place was lost"
            )

    mock_send.assert_called_once_with("something important", sshr)
    mock_reconnect.assert_called_once_with()

    # and now finally check that OSErrors != 5 are re-raised

    fake_os_error.errno = 14

    with pytest.raises(OSError):
        with send_mock as mock_send:
            inter.moved_run("something important")

    mock_send.assert_called_once_with("something important", sshr)


def test_run_thread():
    """If run thread is used the callback should be called with results."""

    runner = Bladerunner()
    inter = runner.interactive("nowhere_really")
    callback = mock.Mock()

    with mock.patch.object(inter, "run", return_value="fake") as mock_run:
        inter._run_thread("fake cmd", callback)

    mock_run.assert_called_once_with("fake cmd")
    callback.assert_called_once_with("fake")


def test_run_threaded():
    """Ensure run threaded returns a started threading.Thread."""

    runner = Bladerunner()
    inter = runner.interactive("somewhere_safe")
    fake_mock = mock.Mock()
    thread_mock = mock.patch.object(
        interactive.threading,
        "Thread",
        return_value=fake_mock,
    )

    with thread_mock as mock_thread:
        inter.run_threaded("some fake command")

    mock_thread.assert_called_once_with(
        target=inter._run_thread,
        args=("some fake command", None),
    )
    assert fake_mock.start.called


def test_connect_thread():
    """If connect thread is used the callback should be called with results."""

    runner = Bladerunner()
    inter = runner.interactive("nowhere_out_there")
    callback = mock.Mock()

    with mock.patch.object(inter, "connect", return_value="ok") as mock_con:
        inter._connect_thread(callback)

    mock_con.assert_called_once_with(status_return=True)
    callback.assert_called_once_with("ok")


def test_connect_threaded():
    """Ensure connect threaded returns a started threading.Thread."""

    runner = Bladerunner()
    inter = runner.interactive("some_safe_place")
    fake_mock = mock.Mock()
    thread_mock = mock.patch.object(
        interactive.threading,
        "Thread",
        return_value=fake_mock,
    )

    with thread_mock as mock_thread:
        inter.connect_threaded()

    mock_thread.assert_called_once_with(
        target=inter._connect_thread,
        args=(None,),
    )
    assert fake_mock.start.called


def test_log(capfd):
    """Ensure the interactive object is logging to stdout correctly."""

    runner = Bladerunner({"debug": True})
    inter = runner.interactive("makes_no_difference")

    inter.log("some message")
    stdout, stderr = capfd.readouterr()

    assert stderr == ""
    assert stdout == "DEBUG: some message\n"


def test_log_no_debug(capfd):
    """If the debug option is not set, nothing should be printed to stdout."""

    runner = Bladerunner()
    inter = runner.interactive("anywhere_at_all")
    inter.log("some words")
    stdout, stderr = capfd.readouterr()
    assert stderr == ""
    assert stdout == ""
