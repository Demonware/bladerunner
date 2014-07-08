#coding: utf-8
"""Bladerunner output formatting functions.

Copyright (c) 2014, Activision Publishing, Inc.
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of Activision Publishing, Inc. nor the names of its
  contributors may be used to endorse or promote products derived from this
  software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""


from __future__ import print_function

import os
import re

from bladerunner.progressbar import get_term_width


class FakeStdOut(object):
    """An object to pass to pexpect's debug logger to simulate sys.stdout."""

    @staticmethod
    def write(string):
        """Fake write, use print instead."""

        print(string.decode("latin-1").strip())

    @staticmethod
    def flush():
        """Fake flush, print will flush."""

        pass


def no_empties(input_list):
    """Searches through a list and tosses empty elements."""

    out_list = []
    for item in input_list:
        if item:
            out_list.append(item.encode("latin-1").decode("latin-1").strip())
    return out_list


def format_output(output, command):
    """Formatting function to strip colours, remove tabs, etc.

    Args::

        output: the pexpect object's before method after issuing the command
        command: the command last issued

    Returns:
        a (hopefully) nicely formatted string of the command's output
    """

    def cmd_in_line(command, line):
        """Checks for long commands wrapping into the output."""

        if len(command) < 60:
            return False

        # how large of command sections we'll look for.
        size = 30
        cmd_split = [command[i:i + size] for i in range(0, len(command), size)]

        for fraction in cmd_split:
            if line.find(fraction) > -1:
                return True

    output = output.splitlines()
    results = []
    # the first line is the command, the last is /probably/ the prompt
    # there can be cases that disobey this though, like exiting without a \n
    for line in output[1:-1]:
        line = format_line(line)
        if line and not cmd_in_line(command, line):
            results.append(line)
    return "\n".join(results)


def format_line(line):
    """Removes whitespace, weird tabs, etc..."""

    for encoding in ["utf-8", "latin-1"]:
        try:
            line = line.decode(encoding)
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
        else:
            break
    else:
        return line  # can't decode this, not sure what to do. pass it back

    line = line.strip(os.linesep)  # can't strip new lines enough
    line = line.replace("\r", "")  # no extra carriage returns
    line = re.sub("\033\[[0-9;]+m", "", line)  # no colours
    line = re.sub("\x1b\[[0-9;]+G", "", line)  # no crazy tabs
    line = re.sub("\\x1b\[m\\x0f", "", line)
    line = re.sub("^\s+", "", line)  # no trailing whitespace
    return line


def consolidate(results):
    """Makes a list of servers and replies, consolidates dupes.

    Args:
        results: the results dictionary from Bladerunner.run

    Returns:
        a results dictionary, with a names key instead of name, containing a
        lists of hosts with matching outputs
    """

    finalresults = []
    for server in results:
        for tempserver in finalresults:
            if tempserver["results"] == server["results"]:
                tempserver["names"].append(server["name"])
                break
        else:
            server["names"] = [server["name"]]
            del server["name"]
            finalresults.append(server)

    return finalresults


def csv_results(results, options=None):
    """Prints the results consolidated and in a CSV-ish fashion.

    Args::

        results: the results dictionary from Bladerunner.run
        options: dictionary with optional keys:
            csv_char: a character or string to separate with
    """

    if "csv_char" in options:
        csv_char = options["csv_char"]
    else:
        csv_char = ","

    write("server{csv}command{csv}result\r\n".format(csv=csv_char), options)
    for server in results:
        for command, command_result in server["results"]:
            server_name = server.get("name")
            if not server_name:  # catch for consolidated results
                server_name = " ".join(server.get("names"))

            command_result = "\n".join(no_empties(command_result.split("\n")))
            write(
                (
                    "{name_quote}{name}{name_quote}{csv}{cmd_quote}{command}"
                    "{cmd_quote}{csv}{res_quote}{result}{res_quote}\r\n"
                ).format(
                    name_quote='"' * int(" " in server_name),
                    name=server_name,
                    csv=csv_char,
                    cmd_quote='"' * int(" " in command),
                    command=command,
                    res_quote='"' * int(" " in command_result),
                    result=command_result,
                ),
                options,
            )


def stacked_results(results, options=None):
    """Display the results in a vertical stack without a frame.

    Args::

        results: the bladerunner result dictionary
        options: the bladerunner options dictionary
    """

    results, options = prepare_results(results, options)
    spacer = False
    for result_set in results:
        if spacer:
            write("=" * options["width"], options, end="\n")

        server_lines = []
        line = []
        for name in result_set["names"]:
            # get the current line length...
            currently = sum([len(x) for x in line]) + + len(line)
            # if the name and space for a comma afterwards fit, add to the line
            if currently + (len(name) * 2) + 1 < options["width"]:
                line.append(name)
            else:
                server_lines.append(", ".join(line + [""]).strip())
                line = [name]

        server_lines.append(", ".join(line))

        write("\n".join(server_lines), options, end="\n")
        write("-" * options["width"], options, end="\n")
        for _, result in result_set["results"]:
            write(result, options, end="\n")

        spacer = True


def prepare_results(results, options=None):
    """Prepare the results and options dictionary for pretty printing.

    Args::

        results: the bladerunner result dictionary
        options: the bladerunner options dictionary

    Returns:
        a tuple of (results, options) after modifying the keys for printing
    """

    if options is None:
        options = {}

    left_len = 0
    already_consolidated = False
    for server in results:
        try:
            if len(str(server["name"])) > left_len:
                left_len = len(str(server["name"]))
        except KeyError:
            # catches passing already consolidated results in
            already_consolidated = True
            for server_name in server["names"]:
                if len(server_name) > left_len:
                    left_len = len(server_name)

    if left_len < 6:
        left_len = 6

    # print characters, defined by options["style"]
    options["chars"] = {
        "top_left": ["┌", "*", "╔", "╭"],
        "top": ["─", "-", "═", "─"],
        "top_right": ["┐", "*", "╗", "╮"],
        "top_down": ["┬", "+", "╦", "┬"],
        "side_left": ["├", "*", "╠", "├"],
        "side": ["│", "|", "║", "│"],
        "middle": ["┼", "+", "╬", "┼"],
        "side_right": ["┤", "*", "╣", "┤"],
        "bot_left": ["└", "*", "╚", "╰"],
        "bot": ["─", "-", "═", "─"],
        "bot_right": ["┘", "*", "╝", "╯"],
        "bot_up": ["┴", "+", "╩", "┴"],
    }

    if not "style" in options or not 3 >= options["style"] >= 0:
        options["style"] = 0

    options["left_len"] = left_len

    try:
        width = options["width"] or get_term_width()
    except KeyError:
        width = get_term_width()
    finally:
        options["width"] = width

    if not already_consolidated:
        results = consolidate(results)

    return (results, options)


def pretty_results(results, options=None):
    """Prints the results in a relatively pretty way.

    Args::

        results: the results dictionary from Bladerunner.run
        options: a dictionary with optional keys.
            style: integer style, from 0-3
            jump_host: the string jumpbox hostname
            width: integer fixed width for output
    """

    results, options = prepare_results(results, options)

    pretty_header(options)

    for result in results:
        _pretty_result(result, options, results)

    write(
        "{left_corner}{left}{up}{right}{right_corner}\n".format(
            left_corner=options["chars"]["bot_left"][options["style"]],
            left=options["chars"]["bot"][options["style"]] * (
                options["left_len"] + 2),
            up=options["chars"]["bot_up"][options["style"]],
            right=options["chars"]["bot"][options["style"]] * (
                options["width"] - options["left_len"] - 5),
            right_corner=options["chars"]["bot_right"][options["style"]],
        ),
        options,
    )


def pretty_header(options):
    """Internal function for printing the header of pretty_results.

    Args::

        options: a dictionary with the following keys:
            width: terminal width, already determined in pretty_results
            chars: the character dictionary map, defined in pretty_results
            left_len: the left side length, defined in pretty_results
            jump_host: a string hostname of the jumpbox (if any)
    """

    jumphost = options.get("jump_host")

    if jumphost:
        write(
            "{l_corner}{left}{down}{right}{down}{jumpbox}{r_corner}\n".format(
                l_corner=options["chars"]["top_left"][options["style"]],
                left=options["chars"]["top"][options["style"]] * (
                    options["left_len"]
                    + 2
                ),
                down=options["chars"]["top_down"][options["style"]],
                right=options["chars"]["top"][options["style"]] * (
                    options["width"]
                    - options["left_len"]
                    - 17
                    - len(jumphost)
                ),
                jumpbox=options["chars"]["top"][options["style"]] * (
                    len(jumphost) + 11
                ),
                r_corner=options["chars"]["top_right"][options["style"]],
            ),
            options,
        )

        write(
            (
                "{side} Server{l_gap} {side} Result{r_gap} {side} Jumpbox: "
                "{jumphost} {side}\n"
            ).format(
                side=options["chars"]["side"][options["style"]],
                l_gap=" " * (options["left_len"] - 6),
                r_gap=" " * (
                    options["width"]
                    - options["left_len"]
                    - 25
                    - len(jumphost)
                ),
                jumphost=jumphost,
            ),
            options,
        )
    else:
        write(
            "{l_corner}{left}{down}{right}{r_corner}\n".format(
                l_corner=options["chars"]["top_left"][options["style"]],
                left=options["chars"]["top"][options["style"]] * (
                    options["left_len"]
                    + 2
                ),
                down=options["chars"]["top_down"][options["style"]],
                right=options["chars"]["top"][options["style"]] * (
                    options["width"]
                    - options["left_len"]
                    - 5
                ),
                r_corner=options["chars"]["top_right"][options["style"]],
            ),
            options,
        )

        write(
            "{side} Server{l_gap} {side} Result{r_gap} {side}\n".format(
                side=options["chars"]["side"][options["style"]],
                l_gap=" " * (options["left_len"] - 6),
                r_gap=" " * (options["width"] - options["left_len"] - 13),
            ),
            options,
        )


def _pretty_result(result, options, consolidated_results):
    """Internal function, ran inside of a loop to print super fancy results.

    Args::

        result: the object iterated over in consolidated_results
        options: the options dictionary from pretty_results
        consolidate_results: the output from consolidate
    """

    result_lines = []
    for command, command_result in result["results"]:
        command_split = no_empties(command_result.split("\n"))
        for command_line in command_split:
            result_lines.append(command_line)

    if len(result_lines or "") > len(result["names"]):
        max_length = len(result_lines)
    else:
        max_length = len(result["names"])

    if consolidated_results.index(result) == 0 and options.get("jump_host"):
        # first split has a bottom up character when using a jumpbox
        write(
            "{l_edge}{left}{middle}{right}{up}{jumpbox}{r_edge}\n".format(
                l_edge=options["chars"]["side_left"][options["style"]],
                left=options["chars"]["top"][options["style"]] * (
                    options["left_len"] + 2),
                middle=options["chars"]["middle"][options["style"]],
                right=options["chars"]["top"][options["style"]] * (
                    options["width"]
                    - options["left_len"]
                    - 17
                    - len(options["jump_host"] or "")
                ),
                up=options["chars"]["bot_up"][options["style"]],
                jumpbox=options["chars"]["top"][options["style"]] * (
                    len(options["jump_host"] or "")
                    + 11
                ),
                r_edge=options["chars"]["side_right"][options["style"]],
            ),
            options,
        )
    else:
        # typical horizontal split
        write(
            "{l_side}{left}{middle}{right}{r_side}\n".format(
                l_side=options["chars"]["side_left"][options["style"]],
                left=options["chars"]["top"][options["style"]] * (
                    options["left_len"] + 2),
                middle=options["chars"]["middle"][options["style"]],
                right=options["chars"]["top"][options["style"]] * (
                    options["width"] - options["left_len"] - 5),
                r_side=options["chars"]["side_right"][options["style"]],
            ),
            options,
        )

    for command in range(max_length):
        # print server name or whitespace, mid mark, and leading space
        try:
            write(
                "{side} {server}{gap} {side} ".format(
                    side=options["chars"]["side"][options["style"]],
                    server=result["names"][command],
                    gap=" " * (options["left_len"] - len(
                        str(result["names"][command]))),
                ),
                options,
            )
        except IndexError:
            write(
                "{side} {gap} {side} ".format(
                    side=options["chars"]["side"][options["style"]],
                    gap=" " * options["left_len"],
                ),
                options,
            )

        # print result line, or whitespace, and side mark
        try:
            write(
                "{result}{gap} {side}\n".format(
                    result=result_lines[command],
                    gap=" " * (
                        options["width"]
                        - options["left_len"]
                        - 7
                        - len(result_lines[command])
                    ),
                    side=options["chars"]["side"][options["style"]],
                ),
                options,
            )
        except IndexError:
            write(
                "{gap} {side}\n".format(
                    gap=" " * (options["width"] - options["left_len"] - 7),
                    side=options["chars"]["side"][options["style"]],
                ),
                options,
            )


def write(string, options, end=""):
    """Writes a line of output to either the output file or stdout.

    Args::

        string: the string to write out
        options: the options dictionary, uses 'output_file' key only
        end: character or empty string to end the print statement with
    """

    if options.get("output_file"):
        with open(options["output_file"], "a") as outputfile:
            outputfile.write("{0}{1}".format(string, end))
    else:
        try:
            print(string, end=end)
        except UnicodeDecodeError as error:
            double_check = _prompt_for_input_on_error(
                "Errored printing the results. Would you like to "
                "write them to a file somewhere instead? ",
                error,
            )

            if double_check.lower().startswith("y"):
                options["output_file"] = _prompt_for_input_on_error(
                    "File name: ",
                    error,
                )
                return write(string, options, end)
            else:
                raise error


def _prompt_for_input_on_error(user_msg, error):
    """Prompt the user with a message. If they try to quit, raise the error.

    Args::

        user_msg: string message to display to the user
        error: Exception class to raise if the user sends KeyboardInterrupt

    Returns:
        the user's reply to the string message
    """

    try:
        return input(user_msg)
    except KeyboardInterrupt:
        raise error
