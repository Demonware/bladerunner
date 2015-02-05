# coding: utf-8
"""Unit tests for Bladerunner's output formatting."""


from __future__ import print_function
from __future__ import unicode_literals

import os
import sys
import pytest
import tempfile
from mock import call
from mock import Mock
from mock import patch

if sys.version_info >= (3,):
    import builtins
else:
    import __builtin__

from bladerunner import formatting


@pytest.fixture
def fake_results():
    """Returns a dummy result set."""

    result_set_a = [
        ("echo 'hello world'", "hello world"),
        ("cat dog", "cat: dog: No such file or directory"),
    ]
    result_set_b = [
        ("echo 'hello world'", "hello world"),
        ("cat cat", "cat: cat: No such file or directory")
    ]

    return [
        {"name": "server_a_1", "results": result_set_a},
        {"name": "server_a_2", "results": result_set_a},
        {"name": "server_a_3", "results": result_set_a},
        {"name": "server_a_4", "results": result_set_a},
        {"name": "server_b_1", "results": result_set_b},
        {"name": "server_b_2", "results": result_set_b},
        {"name": "server_b_3", "results": result_set_b},
        {
            "name": "server_c_1",
            "results": result_set_a + result_set_b,
        },
    ]


@pytest.fixture
def fake_unicode_decode_error():
    """Fixture to provide a fake UnicodeDecodeError Exception class."""

    if sys.version_info > (3,):
        return UnicodeDecodeError("utf-8", bytes("fake", "utf-8"), 1, 1, "ok")
    else:
        return UnicodeDecodeError(str("utf-8"), str("fake"), 1, 1, str("ok"))


@pytest.fixture
def fake_unicode_encode_error():
    """Fixture to provide a fake UnicodeEncodeError Exception class."""

    if sys.version_info > (3,):
        return UnicodeEncodeError("utf-8", "ok", 1, 1, "fake")
    else:
        return UnicodeEncodeError(str("utf-8"), unicode("fake"), 1, 1,
                                  str("ok"))


def assert_all_encodings(string, patched):
    """Asserts the string was encoded/decode with all encodings via mock.

    Args::

        string: the string used in the encode/decode
        patched: the mock.patch.object used in the test
    """

    mock_calls = patched.call_args_list
    for this_call, enc in zip(mock_calls, formatting.DEFAULT_ENCODINGS):
        assert this_call == call(string, enc)


def test_no_empties():
    """No empties should return the same list without empty elements."""

    starting = ["something", "", "else", None, "and", "things", "", r""]
    emptyless = formatting.no_empties(starting)

    assert emptyless == ["something", "else", "and", "things"]


def test_no_empties_encodings(fake_unicode_encode_error):
    """All of DEFAULT_ENCODINGS should be tried on items in the input list."""

    decode_patch = patch.object(
        formatting.codecs,
        "encode",
        side_effect=fake_unicode_encode_error,
    )
    with decode_patch as patched_encode:
        assert formatting.no_empties(["something"]) == []

    assert_all_encodings("something", patched_encode)


def test_format_output():
    """Should remove the first, last, and any line with command in it."""

    command = "super duper secret command"
    fake_output = (
        "someshell# {0}\nlots of interesting\noutput n stuff\nsomeshell#"
    ).format(command)

    if sys.version_info >= (3, 0):
        fake_output = bytes(fake_output, "utf-8")

    output = formatting.format_output(fake_output, command)

    assert output == "lots of interesting\noutput n stuff"


def test_command_in_second_line():
    """Long commands and small terminals can lead to leakage."""

    command = (
        "super secret and long rediculous command that receives so many "
        "arguments it spills over into the next line"
    )
    fake_output = (
        "someshell# {0}\n{1}\nlots of interesting\noutput n stuff\n"
        "someshell#"
    ).format(command[:50], command[50:])

    if sys.version_info >= (3, 0):
        fake_output = bytes(fake_output, "utf-8")

    output = formatting.format_output(fake_output, command)

    assert output == "lots of interesting\noutput n stuff"


def test_unknown_returns_line():
    """Let it fail if the shell cant display it if we can't decode."""

    if sys.version_info >= (3, 0):
        starting = bytes("Everybody loves a 🍔!", "utf-8")
    else:
        starting = "Everybody loves a 🍔!"

    output = formatting.format_line(starting)
    if sys.version_info >= (3, 0):
        # py3 will correctly decode and return a str vs the bytes input
        assert "Everybody loves a" in output
    else:
        assert output == starting


def test_format_line_decode_errors(fake_unicode_decode_error):
    """If no suitable codec can be found, it should return the input line."""

    decode_patch = patch.object(
        formatting.codecs,
        "decode",
        side_effect=fake_unicode_decode_error,
    )

    with decode_patch as patched_decode:
        assert formatting.format_line("sure thing") == "sure thing"

    assert_all_encodings("sure thing", patched_decode)


def test_consolidate_results(fake_results):
    """Consolidate should merge matching server result sets."""

    expected_groups = [
        ["server_a_1", "server_a_2", "server_a_3", "server_a_4"],
        ["server_b_1", "server_b_2", "server_b_3"],
        ["server_c_1"],
    ]

    for result_set in formatting.consolidate(fake_results):
        assert "names" in result_set
        assert isinstance(result_set["names"], list)
        assert not "name" in result_set
        assert result_set["names"] in expected_groups


def test_csv_results(fake_results, capfd):
    """Ensure CSV results print correctly."""

    formatting.csv_results(fake_results)
    stdout, _ = capfd.readouterr()
    assert "server,command,result" in stdout
    for server in fake_results:
        assert server["name"] in stdout
        for _, results in server["results"]:
            assert results in stdout


def test_csv_custom_char(fake_results, capfd):
    """Ensure you can specify the char used in csv_results."""

    options = {"csv_char": "@"}
    formatting.csv_results(fake_results, options)
    stdout, _ = capfd.readouterr()
    assert "server@command@result" in stdout
    for server in fake_results:
        assert server["name"] in stdout
        for _, results in server["results"]:
            assert results in stdout


def test_csv_on_consolidated(fake_results, capfd):
    """CSV results should still work post consolidation."""

    result_set = formatting.consolidate(fake_results)
    formatting.csv_results(result_set, {})
    stdout, _ = capfd.readouterr()
    assert "server,command,result" in stdout
    for server in result_set:
        assert " ".join(server["names"]) in stdout
        for _, results in server["results"]:
            assert results in stdout


def test_prepare_results(fake_results):
    """Ensure the results and options dicts are prepared for printing."""

    results, options = formatting.prepare_results(fake_results, {"width": 101})

    assert options["left_len"] == 10
    assert "chars" in options
    assert options["style"] == 0
    assert options["width"] == 101
    assert "names" in results[0]
    assert not "name" in results[0]


def test_already_consildated(fake_results):
    """Make sure we can consolidate before preparing."""

    results = formatting.consolidate(fake_results)
    with patch.object(formatting, "consolidate") as patched:
        formatting.prepare_results(results)

    assert not patched.called


def test_minimum_left_len(fake_results):
    """Left len should have a minimum of 6 chars."""

    for count, result_set in enumerate(fake_results):
        result_set["name"] = chr(97 + count)

    _, options = formatting.prepare_results(fake_results)
    assert options["left_len"] == 6


def test_pretty_results(fake_results):
    """Ensure pretty results is calling everything it should."""

    with patch.object(formatting, "pretty_header") as patched_header:
        with patch.object(formatting, "_pretty_result") as patched_result:
            with patch.object(formatting, "write") as patched_write:
                formatting.pretty_results(fake_results)

    assert patched_header.called
    assert patched_result.called
    assert patched_write.called


def test_pretty_header(fake_results, capfd):
    """Ensure proper formatting in the header line of pretty_output."""

    _, options = formatting.prepare_results(fake_results)
    formatting.pretty_header(options)
    stdout, _ = capfd.readouterr()

    assert str("Server") in stdout
    assert str("Result") in stdout


def test_header_with_jumphost(fake_results, capfd):
    """The jumphost should appear in the header."""

    options = {"jump_host": "some_server"}
    _, options = formatting.prepare_results(fake_results, options)
    formatting.pretty_header(options)

    stdout, _ = capfd.readouterr()

    assert str("Server") in stdout
    assert str("Result") in stdout
    assert str("Jumpbox") in stdout
    assert str("some_server") in stdout


def test_pretty_result(fake_results, capfd):
    """Ensure pretty results are correctly printed."""

    results, options = formatting.prepare_results(fake_results)

    formatting._pretty_result(results[0], options, results)

    stdout, _ = capfd.readouterr()

    for server in results[0]["names"]:
        assert str(server) in stdout
    for _, result in results[0]["results"]:
        assert str(result) in stdout


def test_bottom_up_in_first_result(fake_results, capfd):
    """The first result when using a jumpbox should have a bot_up char."""

    results, options = formatting.prepare_results(
        fake_results,
        {"jump_host": "some_server", "style": 1},
    )

    formatting._pretty_result(results[0], options, results)

    stdout, _ = capfd.readouterr()

    for server in results[0]["names"]:
        assert str(server) in stdout
    for _, result in results[0]["results"]:
        assert str(result) in stdout

    assert options["chars"]["bot_up"][options["style"]] in stdout


def test_results_max_length(fake_results, capfd):
    """Ensure the vertical alignment with multi line output commands."""

    fake_output = ["many", "lines", "of", "output"]
    fake_results.insert(
        0,
        {
            "name": "server_d_1",
            "results": [("obviously fake", "\n".join(fake_output))],
        }
    )
    results, options = formatting.prepare_results(
        fake_results,
        {"style": 1},
    )

    formatting._pretty_result(results[0], options, results)
    stdout, _ = capfd.readouterr()
    stdout = stdout.splitlines()

    # top line should be a space separators
    topline = str("{0}".format(options["chars"]["top"][options["style"]] * 10))
    assert topline in stdout[0]

    # then it should be the server name, separator and first line of cmd
    assert str("server_d_1") in stdout[1]
    assert options["chars"]["side"][options["style"]] in stdout[1]

    # then the multi line command should fill down the right column
    for line, fake_out in enumerate(fake_output, 1):
        assert str(fake_out) in stdout[line]

    # finally check total length
    assert len(stdout) == 5


def test_writing_to_file():
    """Ensure we can write out to a file."""

    string = "some string with words and stuff in it"
    options = {"output_file": tempfile.mktemp()}
    formatting.write(string, options)
    with open(options["output_file"], "r") as openoutput:
        assert string in openoutput.read()


def test_errors_writing_to_stdout(fake_unicode_decode_error):
    """We should prompt the user if there's an error printing."""

    fallback_file = tempfile.mktemp()

    mock_input = patch.object(
        formatting,
        "_prompt_for_input_on_error",
        side_effect=["yes", fallback_file]
    )

    if sys.version_info > (3,):
        m_print = Mock(
            "builtins.print",
            side_effect=fake_unicode_decode_error,
        )
        print_patch = patch.object(builtins, "print", new=m_print)
    else:
        m_print = Mock(
            "__builtin__.print",
            side_effect=fake_unicode_decode_error,
        )
        print_patch = patch.object(__builtin__, str("print"), new=m_print)

    with print_patch:
        with mock_input:
            formatting.write("super important data", {})

    assert os.path.exists(fallback_file)

    with open(fallback_file, "r") as openfile:
        assert "super important data" in openfile.read()


def test_write_encoding_errors(fake_unicode_decode_error):
    """All encodings should be tried, then finally a fallback to prompt."""

    open_patch = patch.object(
        formatting.io,
        "open",
        side_effect=fake_unicode_decode_error,
    )
    with open_patch as p_open:
        with patch.object(formatting, "_retry_write") as patched_retry:
            formatting.write("some stuff", {"output_file": "yep"}, "\o/")

    patched_retry.assert_called_once_with(
        "some stuff",
        {"output_file": "yep"},
        "\o/",
    )

    for call_, enc in zip(p_open.call_args_list, formatting.DEFAULT_ENCODINGS):
        assert call_ == call("yep", "a", encoding=enc)


def test_user_requested_raise(fake_unicode_decode_error):
    """If the user doesn't answer "yes", raise the error during write."""

    mock_input = patch.object(
        formatting,
        "_prompt_for_input_on_error",
        return_value="no",
    )

    if sys.version_info > (3,):
        m_print = Mock(
            "builtins.print",
            side_effect=fake_unicode_decode_error,
        )
        print_patch = patch.object(builtins, "print", new=m_print)
    else:
        m_print = Mock(
            "__builtin__.print",
            side_effect=fake_unicode_decode_error,
        )
        print_patch = patch.object(__builtin__, str("print"), new=m_print)

    with pytest.raises(SystemExit) as err:
        with print_patch:
            with mock_input:
                formatting.write("super important data", {})

    assert err.exconly() == (
        "SystemExit: Could not write results. Cancelled on user request."
    )


def test_prompt_for_user_input():
    """Make sure we prompt the user with the string provided."""

    error = IOError("totes fake")

    if sys.version_info > (3,):
        mock_input = Mock("builtins.input", return_value="words")
        input_patch = patch.object(builtins, "input", new=mock_input)
    else:
        mock_input = Mock("__builtin__.raw_input", return_value="words")
        input_patch = patch.object(__builtin__, "raw_input", new=mock_input)

    with input_patch as patched:
        formatting._prompt_for_input_on_error("prompted with:", error)

    patched.assert_called_once_with("prompted with:")


def test_raise_error_during_prompt():
    """Ensure the original exception is raised if the user sends ^C."""

    error = OSError("totes fake")

    if sys.version_info > (3,):
        mock_input = Mock("builtins.input", side_effect=KeyboardInterrupt)
        input_patch = patch.object(builtins, "input", new=mock_input)
    else:
        mock_input = Mock(
            "__builtin__.raw_input",
            side_effect=KeyboardInterrupt,
        )
        input_patch = patch.object(__builtin__, "raw_input", new=mock_input)

    with pytest.raises(OSError) as raised_error:
        with input_patch as patched:
            formatting._prompt_for_input_on_error("prompted with:", error)

    patched.assert_called_once_with("prompted with:")
    assert "OSError: totes fake" == raised_error.exconly()


def test_fake_stdout_decode():
    """Make sure we are cleaning up the output strings correctly."""

    with patch.object(formatting.codecs, "decode") as decode_patch:
        fakestdout = formatting.FakeStdOut()
        fakestdout.write("words")

    decode_patch.assert_called_once_with("words", formatting.DEFAULT_ENCODING)


def test_fake_stdout_decode_failures(fake_unicode_decode_error):
    """All of the DEFAULT_ENCODINGS should be tried when printing."""

    decode_patch = patch.object(formatting.codecs, "decode",
                                side_effect=fake_unicode_decode_error)
    fakestdout = formatting.FakeStdOut()
    with decode_patch as patched_decode:
        fakestdout.write("things")

    assert_all_encodings("things", patched_decode)


def test_fake_stdout_flush():
    """Just ensure the attribute exists, we don't have to flush."""

    fakeout = formatting.FakeStdOut()
    assert "flush" in dir(fakeout)

    # code inspection to ensure the function isn't doing anything
    assert fakeout.flush.__code__.co_varnames == ()
    assert fakeout.flush.__code__.co_nlocals == 0
    assert fakeout.flush.__code__.co_stacksize == 1


def test_stacked_results(fake_results, capfd):
    """Ensure the formatting for stacked/flat results."""

    formatting.stacked_results(fake_results, {"width": 55})

    stdout, _ = capfd.readouterr()

    expected = [
        "server_a_1, server_a_2, server_a_3, server_a_4",
        "-------------------------------------------------------",
        "hello world",
        "cat: dog: No such file or directory",
        "=======================================================",
        "server_b_1, server_b_2, server_b_3",
        "-------------------------------------------------------",
        "hello world",
        "cat: cat: No such file or directory",
        "=======================================================",
        "server_c_1",
        "-------------------------------------------------------",
        "hello world",
        "cat: dog: No such file or directory",
        "hello world",
        "cat: cat: No such file or directory\n",
    ]

    assert stdout == "\n".join(expected)


def test_stacked_multiline_servers(fake_results, capfd):
    """If width is narrow enough it should list servers on multiple lines."""

    formatting.stacked_results(fake_results, {"width": 45})

    stdout, _ = capfd.readouterr()

    expected = [
        "server_a_1, server_a_2, server_a_3,",
        "server_a_4",
        "---------------------------------------------",
        "hello world",
        "cat: dog: No such file or directory",
        "=============================================",
        "server_b_1, server_b_2, server_b_3",
        "---------------------------------------------",
        "hello world",
        "cat: cat: No such file or directory",
        "=============================================",
        "server_c_1",
        "---------------------------------------------",
        "hello world",
        "cat: dog: No such file or directory",
        "hello world",
        "cat: cat: No such file or directory\n",
    ]

    assert stdout == "\n".join(expected)


def test_all_passwords_are_hidden():
    """Passwords from Bladerunner.options should be hidden in the output.

    You could use --debug=<int> from the command line to see the unfiltered
    output of all commands, but passwords will be hidden in formatted output.
    """

    options = {
        "password": "hunter7",
        "second_password": "something secret",
        "jump_password": "shared_password",
    }
    output = (
        "shell_prompt> faked\n"
        "some text which has hunter7 in it, something secret and even a"
        "shared_password as well, crazy.\n"
        "shell_prompt>"
    )
    expected = (
        "some text which has ******* in it, **************** and even a"
        "*************** as well, crazy."
    )

    if sys.version_info > (3,):
        output = bytes(output, "utf-8")

    assert formatting.format_output(output, "faked", options) == expected
