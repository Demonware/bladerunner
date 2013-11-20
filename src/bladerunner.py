#!/usr/bin/env python
#coding: utf-8

"""Bladerunner version 3.5. Released July 25, 2013. Written in Python 2.7.

Provides a method of pushing changes or running audits on groups of similar
hosts over SSH using pexpect (http://pexpect.sourceforge.net). Can be extended
to utilize an intermediary host in the event of networking restrictions.

Copyright (c) 2013, Activision Publishing, Inc.
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


from __future__ import unicode_literals
import os
import re
import sys
import math
import time
import socket
import getpass
import pexpect
from concurrent.futures import ThreadPoolExecutor

from .cmdline import cmdline_entry
from .progressbar import ProgressBar
from .progressbar import get_term_width


class Bladerunner(object):
    """Main logic for the serial execution of commands on hosts.

    Initialized by a dictionary with the following optional keys::

        username: string username, or getpass will guess.
        password: string plain text password, if required.
        ssh_key: string non-default ssh key file location.
        delay: integer in seconds to pause between servers.
        extra_prompts: list of strings of additional expect prompts.
        width: integer terminal width for output, or it uses all.
        jump_host: string hostname of intermediary host.
        jump_user: alternate username for jump_host.
        jump_password: alternate password for jump_host.
        second_password: an additional different password for commands.
        password_safety: check if the first login succeeds first (False).
        cmd_timeout: integer in seconds to wait for commands (20).
        timeout: integer in seconds to wait to connect (20).
        threads: integer number of parallel threads to run (100)
        style: integer for outputting. Between 0-3 are pretty, or CSV.
        csv_char: string character to use for CSV results.
        progressbar: boolean to declare if we want a progress display.
    """

    def __init__(self, options=None):
        """Fills in the options dictionary with any missing keys."""

        if not options:
            options = {}

        defaults = {
            "cmd_timeout": 20,
            "csv_char": ",",
            "delay": None,
            "extra_prompts": [],
            "jump_host": None,
            "jump_password": None,
            "jump_user": None,
            "password": None,
            "password_safety": False,
            "progressbar": False,
            "second_password": None,
            "ssh_key": None,
            "style": 0,
            "threads": 100,
            "timeout": 20,
            "username": None,
            "width": None,
        }

        for key, value in defaults.items():
            if not key in options:
                options[key] = value

        options = set_shells(options)

        self.options = options

        self.errors = [
            "Did not login correctly (err: -1)",
            "Received unexpected password prompt (err: -2)",
            "Could not resolve host (err: -3)",
            "Permission denied (err: -4)",
            "Password denied (err: -5)",
            "Shell prompt guessing failure (err: -6)",
        ]

        self.progress = None
        self.sshc = None
        self.commands = None

        super(Bladerunner, self).__init__()

    def run(self, commands, servers):
        """Executes commands on servers.

        Args::

            commands: a list of strings of commands to run
            servers: a list of strings of hostnames

        Returns:
            a list of dictionaries with two keys: name, and results. results
            is a list of tuples of commands issued and their replies.
        """

        if not isinstance(servers, list):
            servers = [servers]

        if not isinstance(commands, list):
            commands = [commands]

        self.commands = commands

        if self.options["progressbar"]:
            self.progress = ProgressBar(len(servers), self.options)
            self.progress.setup()

        if self.options["jump_host"]:
            jumpuser = self.options["jump_user"] or self.options["username"]
            (self.sshc, error_code) = self.connect(
                self.options["jump_host"],
                jumpuser,
                self.options["jump_pass"],
                self.options["jump_port"]
            )
            if error_code < 0:
                message = int(math.fabs(error_code)) - 1
                raise SystemExit("Jumpbox Error: {}".format(
                    self.errors[message]))

        if self.options["delay"] or self.options["jump_host"]:
            results = self._run_serial(servers)
        else:
            results = self._run_parallel(servers)

        if self.options["jump_host"]:
            self.close(self.sshc, True)

        if self.options["progressbar"]:
            self.progress.clear()

        return results

    def _run_parallel(self, servers):
        """Runs commands on servers in parallel when not using a jumpbox."""

        if self.options["password_safety"]:
            return self._run_parallel_safely(servers)
        else:
            return self._run_parallel_no_check(servers)

    def _run_parallel_no_check(self, servers):
        """Runs all servers in parallel without checking if any succeed first.

        Could potentially insta-lock an LDAP account... but we're called from
        lib here so hopefully people know what they're doing. Command line
        entry will default to _run_parallel_safely(). Also called from _safely.

        Args:
            servers: the list of servers to run
        """

        results = []

        max_threads = self.options["threads"]
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            for result_dict in executor.map(self._run_single, servers):
                results.append(result_dict)

        return results

    def _run_parallel_safely(self, servers):
        """Runs commands in parallel after checking the success of first login.

        Args:
            servers: the list of servers to run
        """

        results = []
        sshr, error_code = self.connect(
            servers[0],
            self.options["username"],
            self.options["password"],
            self.options['port'],
        )
        if error_code < 0:
            message = int(math.fabs(error_code)) - 1
            results.append({
                "name": servers[0],
                "results": [("login", self.errors[message])],
            })
            return results + self._run_serial(
                servers[1:],
            )
        else:
            results.append(self.send_commands(sshr, servers[0]))
            self.close(sshr, not self.options["jump_host"])
            sshr = None
            if self.options["progressbar"]:
                self.progress.update()

            return results + self._run_parallel_no_check(servers[1:])

    def _run_serial(self, servers):
        """Runs commands on servers in serial after jumpbox."""

        results = []
        for server in servers:
            if self.options["delay"] and servers.index(server) > 0:
                time.sleep(self.options["delay"])
            results.append(self._run_single(server))
        return results

    def _run_single(self, server):
        """Runs commands on a single server."""

        (sshr, error_code) = self.connect(
            server,
            self.options["username"],
            self.options["password"],
            self.options['port'],
        )
        if error_code < 0:
            message = int(math.fabs(error_code)) - 1
            results = {
                "name": server,
                "results": [("login", self.errors[message])],
            }
        else:
            results = self.send_commands(sshr, server)
            self.close(sshr, not self.options["jump_host"])
            sshr = None

        if self.options["progressbar"]:
            self.progress.update()

        return results

    def _send_cmd(self, command, server):
        """Internal method to send a single command to the pexpect object.

        Args::

            command: the command to send
            server: the pexpect object to send to

        Returns:
            The formatted output of the command as a string, or -1 on timeout
        """

        try:
            server.sendline(command)
            cmd_response = server.expect(
                self.options["shell_prompts"] +
                self.options["extra_prompts"] +
                self.options["passwd_prompts"],
                self.options["cmd_timeout"],
            )

            if cmd_response >= (
                len(self.options["shell_prompts"]) +
                len(self.options["extra_prompts"])
            ) and len(self.options["second_password"]) > 0:
                server.sendline(self.options["second_password"])
                server.expect(
                    self.options["shell_prompts"] +
                    self.options["extra_prompts"],
                    self.options["cmd_timeout"],
                )
        except (pexpect.TIMEOUT, pexpect.EOF):
            return self._try_for_unmatched_prompt(
                server,
                server.before,
                command,
            )

        return format_output(server.before, command)

    def _try_for_unmatched_prompt(self, server, output, command,
                                  _from_login=False, _attempts_left=3):
        """On command timeout, send newlines to guess the missing shell prompt.

        Args:

            server: the sshc object
            output: the sshc.before after issuing command before the timeout
            command: the command issued that caused the initial timeout
            _from_login: if this is called from the login method, return the
                         (connection, code) tuple, or return formatted_output()
            _attempts_left: internal integer to iterate over this function with

        Returns:
            format_output if it can find a new prompt, or -1 on error
        """

        # guess the shell to be in the last 30 chars of the last line of output
        new_prompt = _format_line(output.splitlines()[-1][-30:])

        # escape regex characters
        replacements = ["\\", "/", ")", "(", "[", "]", "{", "}", " ", "$", "?",
                        ">", "<", "^", ".", "*"]
        for char in replacements:
            new_prompt = new_prompt.replace(char, "\{}".format(char))

        if new_prompt and new_prompt not in self.options["shell_prompts"]:
            self.options["shell_prompts"].append(new_prompt)

        try:
            server.sendline()
            server.expect(
                self.options["shell_prompts"] +
                self.options["extra_prompts"],
                2,
            )
        except (pexpect.TIMEOUT, pexpect.EOF):
            if _attempts_left:
                return self._try_for_unmatched_prompt(
                    server,
                    server.before,
                    command,
                    _from_login=_from_login,
                    _attempts_left=(_attempts_left - 1),
                )
        else:
            self._push_expect_forward(server)
            if _from_login:
                return (server, 1)
            else:
                return format_output(output, command)

        self.send_interrupt(server)

        if _from_login:
            # if we get here, we tried to guess the prompt by sending enter 3
            # times, but still didn't return to that same shell. Something odd
            # is likely happening on the device that needs manual inspection
            return (None, -6)
        else:
            return -1

    def send_commands(self, server, hostname):
        """Executes the commands on a pexpect object.

        Args::

            server: the pexpect host object
            hostname: the string hostname of the server

        Returns:
            a dictionary with two keys::

                name: string of the server's hostname
                results: a list of tuples with each command and its result
        """

        results = {"name": hostname}
        command_results = []
        for command in self.commands:
            command_result = self._send_cmd(command, server)
            if not command_result or command_result == "\n":
                command_results.append((
                    command,
                    "no output from: {}".format(command),
                ))
            elif command_result == -1:
                command_results.append((
                    command,
                    "did not return after issuing: {}".format(command),
                ))
            else:
                command_results.append((command, command_result))

        results["results"] = command_results
        return results

    def connect(self, target, username, password, port):
        """Connects to a server, maybe from another server.

        Args::

            target: the hostname, as a string
            username: the user we are connecting as
            password: plain text password to pass
            port: ssh port number, as integer

        Returns:
            a pexpect object that can be passed back here or to send_commands()
        """

        if not _can_resolve(target):
            return (None, -3)

        if not self.sshc:
            try:
                if self.options["ssh_key"] and \
                   os.path.isfile(self.options["ssh_key"]):
                    sshr = pexpect.spawn(
                        "ssh -p {portnumber} -ti {key} {user}@{host}".format(
                            portnumber=port,
                            key=self.options["ssh_key"],
                            user=username,
                            host=target,
                        )
                    )
                else:
                    sshr = pexpect.spawn(
                        "ssh -p {portnumber} -t {user}@{host}".format(
                            portnumber=port,
                            user=username,
                            host=target,
                        )
                    )
                login_response = sshr.expect(
                    self.options["passwd_prompts"] +
                    self.options["shell_prompts"] +
                    self.options["extra_prompts"],
                    self.options["timeout"],
                )

                if self.options["jump_host"]:
                    self.sshc = sshr
                    return self.login(self.sshc, password, login_response)
                else:
                    return self.login(sshr, password, login_response)
            except (pexpect.TIMEOUT, pexpect.EOF):
                return (None, -1)
        else:
            if self.options["ssh_key"]:
                self.sshc.sendline("ssh -ti {key} {user}@{host}".format(
                    key=self.options["ssh_key"],
                    user=username,
                    host=target,
                ))
            else:
                self.sshc.sendline("ssh -t {user}@{host}".format(
                    user=username,
                    host=target,
                ))

            try:
                login_response = self.sshc.expect(
                    self.options["passwd_prompts"] +
                    self.options["shell_prompts"] +
                    self.options["extra_prompts"],
                    self.options["timeout"],
                )
            except (pexpect.TIMEOUT, pexpect.EOF):
                self.send_interrupt(self.sshc)
                return (None, -1)

            if self.sshc.before.find("Permission denied") != -1:
                self.send_interrupt(self.sshc)
                return (None, -4)

            return self.login(self.sshc, password, login_response)

    def login(self, sshc, password, login_response):
        """Internal method for logging in, used by connect.

        Args::

            sshc: the pexpect object
            password: plain text password to send
            login_response: the pexpect return status integer

        Returns:
            a tuple of the connection object and error code
        """

        passlen = len(self.options["passwd_prompts"])

        if login_response == 0:
            # new identity for known_hosts file
            sshc.sendline("yes")
            try:
                login_response = sshc.expect(
                    self.options["passwd_prompts"] +
                    self.options["shell_prompts"] +
                    self.options["extra_prompts"],
                    self.options["timeout"],
                )
            except (pexpect.TIMEOUT, pexpect.EOF):
                self.send_interrupt(sshc)
                return (None, -1)

        if login_response <= passlen and password:
            # password prompt as expected
            sshc.sendline(password)
            try:
                send_response = sshc.expect(
                    self.options["passwd_prompts"] +
                    self.options["shell_prompts"] +
                    self.options["extra_prompts"],
                    self.options["timeout"],
                )
            except (pexpect.TIMEOUT, pexpect.EOF):
                # guess the shell prompt here, we're potentially logged in
                return self._try_for_unmatched_prompt(
                    sshc,
                    sshc.before,
                    "login",
                    _from_login=True,
                )

            if send_response <= len(self.options["passwd_prompts"]):
                # wrong password, or received another password prompt
                self.send_interrupt(sshc)
                return (sshc, -5)
            else:
                # logged in properly with a password
                return (sshc, 1)

        elif login_response <= passlen and not password:
            # password prompt not expected
            self.send_interrupt(sshc)
            return (None, -2)
        else:
            # logged in without using a password. we could check to see
            # if this was intended or not, but really, the point is we've
            # logged into the box, it's time to issue some commands and GTFO
            return (sshc, 1)

    def send_interrupt(self, sshc):
        """Sends ^c and pushes pexpect forward on the object.

        Args:
            sshc: the pexpect object

        Returns:
            None: the sshc maintains its state and should be ready for use
        """

        if not self.options["jump_host"]:
            return
        try:
            sshc.sendline("\003")
            sshc.expect(
                self.options["shell_prompts"] +
                self.options["extra_prompts"],
                3,
            )
        except (pexpect.TIMEOUT, pexpect.EOF):
            pass
        self._push_expect_forward(sshc)

    def _push_expect_forward(self, sshc):
        """Moves the expect object forwards.

        Args:
            sshc: the pexpect object you'd like to move up
        """

        try:
            sshc.expect(
                self.options["shell_prompts"] +
                self.options["extra_prompts"],
                2,
            )
        except (pexpect.TIMEOUT, pexpect.EOF):
            pass
        try:
            sshc.expect(
                self.options["shell_prompts"] +
                self.options["extra_prompts"],
                2,
            )
        except (pexpect.TIMEOUT, pexpect.EOF):
            pass

    def close(self, sshc, terminate):
        """Closes a connection object.

        Args::

            sshc: the pexpect object to close
            terminate: a boolean value to terminate all connections or not

        Returns:
            None: the sshc will be at the jumpbox, or the connection is closed
        """

        sshc.sendline("exit")

        if terminate:
            sshc.terminate()
        else:
            try:
                sshc.expect(
                    self.options["shell_prompts"] +
                    self.options["extra_prompts"],
                    self.options["cmd_timeout"],
                )
            except (pexpect.TIMEOUT, pexpect.EOF):
                pass


def _can_resolve(target):
    """Tries to look up a hostname then bind to that IP address.

    Args:
        target: a hostname or IP address as a string

    Returns:
        True if the target is resolvable to a valid IP address
    """

    try:
        socket.getaddrinfo(target, None)
        return True
    except socket.error:
        return False


def no_empties(input_list):
    """Searches through a list and tosses empty elements."""

    output_list = []
    for item in input_list:
        if item:
            output_list.append(item)
    return output_list


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

    output = output.split("\r\n")  # TTY connections use CRLF line-endings
    results = []
    for line in output[1:-1]:
        line = _format_line(line)
        if not cmd_in_line(command, line):
            results.append(line)
    return "\n".join(results)


def _format_line(line):
    """Removes whitespace, weird tabs, etc..."""

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
            if not tempserver:
                continue
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

    sys.stdout.write("server,command,result\r\n")
    for server in results:
        for command, command_result in server["results"]:
            command_result = "\n".join(no_empties(command_result.split("\n")))
            sys.stdout.write((
                "{name_quote}{name}{name_quote}{csv}{cmd_quote}{command}"
                "{cmd_quote}{csv}{res_quote}{result}{res_quote}\r\n"
            ).format(
                name_quote='"' * int(" " in server["name"]),
                name=server['name'],
                csv=csv_char,
                cmd_quote='"' * int(" " in command),
                command=command,
                res_quote='"' * int(" " in command_result),
                result=command_result,
            ))


def pretty_results(results, options=None):
    """Prints the results in a relatively pretty way.

    Args::

        results: the results dictionary from Bladerunner.run
        options: a dictionary with optional keys.
            style: integer style, from 0-3
            jump_host: the string jumpbox hostname
            width: integer fixed width for output
    """

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

    # print characters, defined by options['style']
    chars = {
        "topLeft": ["┌", "*", "╔", "╭"],
        "top": ["─", "-", "═", "─"],
        "topRight": ["┐", "*", "╗", "╮"],
        "topDown": ["┬", "+", "╦", "┬"],
        "sideLeft": ["├", "*", "╠", "├"],
        "side": ["│", "|", "║", "│"],
        "middle": ["┼", "+", "╬", "┼"],
        "sideRight": ["┤", "*", "╣", "┤"],
        "botLeft": ["└", "*", "╚", "╰"],
        "bot": ["─", "-", "═", "─"],
        "botRight": ["┘", "*", "╝", "╯"],
        "botUp": ["┴", "+", "╩", "┴"],
    }

    if not options:
        options = {}

    try:
        assert 3 >= options["style"] >= 0
    except (AssertionError, KeyError):
        options["style"] = 0

    options["left_len"] = left_len
    options["chars"] = chars

    try:
        width = options["width"] or get_term_width()
    except KeyError:
        width = get_term_width()

    options["width"] = width

    pretty_header(options)

    if not already_consolidated:
        results = consolidate(results)

    for result in results:
        _pretty_result(result, options, results)

    sys.stdout.write("{left_corner}{left}{up}{right}{right_corner}\n".format(
        left_corner=chars["botLeft"][options["style"]],
        left=chars["bot"][options["style"]] * (left_len + 2),
        up=chars["botUp"][options["style"]],
        right=chars["bot"][options["style"]] * (width - left_len - 5),
        right_corner=chars["botRight"][options["style"]],
    ))


def pretty_header(options):
    """Internal function for printing the header of pretty_results.

    Args::

        options: a dictionary with the following keys:
            width: terminal width, already determined in pretty_results
            chars: the character dictionary map, defined in pretty_results
            left_len: the left side length, defined in pretty_results
            jump_host: a string hostname of the jumpbox (if any)
    """

    if "jump_host" in options:
        jumphost = options["jump_host"]
    else:
        jumphost = None

    if jumphost:
        sys.stdout.write((
            "{left_corner}{left}{down}{right}{down}{jumpbox}{right_corner}\n"
        ).format(
            left_corner=options["chars"]["topLeft"][options["style"]],
            left=options["chars"]["top"][options["style"]] * (
                options["left_len"]
                + 2
            ),
            down=options["chars"]["topDown"][options["style"]],
            right=options["chars"]["top"][options["style"]] * (
                options["width"]
                - options["left_len"]
                - 17
                - len(jumphost)
            ),
            jumpbox=options["chars"]["top"][options["style"]] * (
                len(jumphost) + 11
            ),
            right_corner=options["chars"]["topRight"][options["style"]],
        ))

        sys.stdout.write((
            "{side} Server{left_gap} {side} Result{right_gap} {side} Jumpbox: "
            "{jumphost} {side}\n"
        ).format(
            side=options["chars"]["side"][options["style"]],
            left_gap=" " * (options["left_len"] - 6),
            right_gap=" " * (
                options["width"]
                - options["left_len"]
                - 25
                - len(jumphost)
            ),
            jumphost=jumphost,
        ))
    else:
        sys.stdout.write((
            "{left_corner}{left}{down}{right}{right_corner}\n"
        ).format(
            left_corner=options["chars"]["topLeft"][options["style"]],
            left=options["chars"]["top"][options["style"]] * (
                options["left_len"]
                + 2
            ),
            down=options["chars"]["topDown"][options["style"]],
            right=options["chars"]["top"][options["style"]] * (
                options["width"]
                - options["left_len"]
                - 5
            ),
            right_corner=options["chars"]["topRight"][options["style"]],
        ))

        sys.stdout.write((
            "{side} Server{left_gap} {side} Result{right_gap} {side}\n"
        ).format(
            side=options["chars"]["side"][options["style"]],
            left_gap=" " * (options["left_len"] - 6),
            right_gap=" " * (options["width"] - options["left_len"] - 13),
        ))


def _pretty_result(result, options, consolidated_results):
    """Internal function, ran inside of a loop to print super fancy results.

    Args::

        result: the object iterated over in consolidated_results
        options: the options dictionary from pretty_results
        consolidate_results: the output from consolidate
    """

    chars = options["chars"]
    left_len = options["left_len"]
    width = options["width"]

    result_lines = []
    for command, command_result in result["results"]:
        command_split = no_empties(command_result.split("\n"))
        for command_line in command_split:
            result_lines.append(command_line)

    if len(result_lines) > len(result["names"]):
        max_length = len(result_lines)
    else:
        max_length = len(result["names"])

    if consolidated_results.index(result) == 0 and "jump_host" in options \
       and options["jump_host"]:
        # first split has a bottom up character when using a jumpbox
        sys.stdout.write((
            "{left_edge}{left}{middle}{right}{up}{jumpbox}{right_edge}\n"
        ).format(
            left_edge=chars["sideLeft"][options["style"]],
            left=chars["top"][options["style"]] * (left_len + 2),
            middle=chars["middle"][options["style"]],
            right=chars["top"][options["style"]] * (
                width
                - left_len
                - 17
                - len(options["jump_host"] or "")
            ),
            up=chars["botUp"][options["style"]],
            jumpbox=chars["top"][options["style"]] * (
                len(options["jump_host"] or "")
                + 11
            ),
            right_edge=chars["sideRight"][options["style"]],
        ))
    else:
        # typical horizontal split
        sys.stdout.write((
            "{left_side}{left}{middle}{right}{right_side}\n"
        ).format(
            left_side=chars["sideLeft"][options["style"]],
            left=chars["top"][options["style"]] * (left_len + 2),
            middle=chars["middle"][options["style"]],
            right=chars["top"][options["style"]] * (width - left_len - 5),
            right_side=chars["sideRight"][options["style"]],
        ))

    for command in range(max_length):
        # print server name or whitespace, mid mark, and leading space
        try:
            sys.stdout.write("{side} {server}{gap} {side} ".format(
                side=chars["side"][options["style"]],
                server=result["names"][command],
                gap=" " * (left_len - len(str(result["names"][command]))),
            ))
        except IndexError:
            sys.stdout.write("{side} {gap} {side} ".format(
                side=chars["side"][options["style"]],
                gap=" " * left_len,
            ))

        # print result line, or whitespace, and side mark
        try:
            sys.stdout.write("{result}{gap} {side}\n".format(
                result=result_lines[command],
                gap=" " * (
                    width
                    - left_len
                    - 7
                    - len(str(result_lines[command]))
                ),
                side=chars["side"][options["style"]],
            ))
        except IndexError:
            sys.stdout.write("{gap} {side}\n".format(
                gap=" " * (width - left_len - 7),
                side=chars["side"][options["style"]],
            ))


def set_shells(options):
    """Set password, shell and extra prompts for the username.

    Args:
        options dictionary with username, jump_user and extra_prompts keys.

    Returns:
        options dictionary with shell_prompts and passwd_prompts keys
    """

    shells = [
        "mysql\\>",
        "ftp\\>",
        "telnet\\>",
        "\\[root\\@.*\\]\\#",
        "root\\@.*\\:\\~\\#",
    ]
    password_shells = ["(yes/no)\\\?", "assword:"]

    if not options["username"]:
        options["username"] = getpass.getuser()

    shells.append("\\[{}@.*\\]\\$".format(options["username"]))
    shells.append("{}@.*:~\\$".format(options["username"]))
    password_shells.append("{}@.*assword\\:".format(options["username"]))
    password_shells.append("{}\\:".format(options["username"]))

    if options["jump_user"]:
        shells.append("\\[{}@.*\\]\\$".format(options["jump_user"]))
        shells.append("{}@.*:~\\$".format(options["jump_user"]))
        password_shells.append("{}@.*assword:".format(options["jump_user"]))
        password_shells.append("{}:".format(options["jump_user"]))

    options["shell_prompts"] = shells
    options["passwd_prompts"] = password_shells
    return options


def main_exit(results, options):
    """A buffer for selecting the correct output function and exiting.

    Args::

        results: the results dictionary from Bladerunner.run
        options: the options dictionary, uses 'style' key only
    """

    if options["style"] < 0 or options["style"] > 3:
        csv_results(results, options)
    else:
        try:
            pretty_results(results, options)
        except UnicodeEncodeError:
            csv_results(results, options)
    raise SystemExit


if __name__ == "__main__":
    COMMANDS, SERVERS, OPTIONS = cmdline_entry()
    BLADERUNNER = Bladerunner(OPTIONS)
    try:
        RESULTS = BLADERUNNER.run(COMMANDS, SERVERS)
        main_exit(RESULTS, OPTIONS)
    except KeyboardInterrupt:
        raise SystemExit("\n")
