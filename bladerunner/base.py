"""Bladerunner provides a method of pushing changes or running audits on groups
of similar hosts over SSH using pexpect (http://pexpect.sourceforge.net). Can
be extended to use an intermediary host if there are networking restrictions.

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


from __future__ import unicode_literals
import os
import sys
import math
import time
import getpass
import pexpect
import threading
from concurrent.futures import ThreadPoolExecutor

from bladerunner.progressbar import ProgressBar
from bladerunner.networking import can_resolve, ips_in_subnet
from bladerunner.formatting import format_line, format_output


class Bladerunner(object):
    """Main logic for the serial execution of commands on hosts.

    Initialized by a dictionary with the following optional keys (defaults)::

        username: string username (None/current user)
        password: string plain text password, if required (None)
        ssh_key: string non-default ssh key file location (None)
        delay: integer in seconds to pause between servers (None)
        extra_prompts: list of strings of additional expect prompts ([])
        width: integer terminal width for output, or it uses all (None/guess)
        jump_host: string hostname of intermediary host (None)
        jump_user: alternate username for jump_host (None)
        jump_password: alternate password for jump_host (None)
        jump_port: SSH port for jump_host (22)
        second_password: an additional different password for commands (None)
        password_safety: check if the first login succeeds first (False)
        port: SSH port for the servers (22)
        cmd_timeout: integer in seconds to wait for commands (20)
        timeout: integer in seconds to wait to connect (20)
        threads: integer number of parallel threads to run (100)
        style: integer for outputting. Between 0-3 are pretty, or CSV (0)
        csv_char: string character to use for CSV results (",")
        progressbar: boolean to declare if we want a progress display (False)
        unix_line_endings: force sending LF as line endings for commands
        windows_line_endings: force sending CRLF as line endings for commands
    """

    def __init__(self, options=None):
        """Fills in the options dictionary with any missing keys."""

        if not options:
            options = {}

        defaults = {
            "cmd_timeout": 20,
            "csv_char": ",",
            "debug": False,
            "delay": None,
            "extra_prompts": [],
            "jump_host": None,
            "jump_password": None,
            "jump_user": None,
            "jump_port": 22,
            "output_file": False,
            "password": None,
            "password_safety": False,
            "port": 22,
            "progressbar": False,
            "second_password": None,
            "ssh_key": None,
            "style": 0,
            "threads": 100,
            "timeout": 20,
            "unix_line_endings": False,
            "username": None,
            "width": None,
            "windows_line_endings": False,
        }

        for key, value in defaults.items():
            if not key in options:
                options[key] = value

        options = _set_shells(options)

        self.options = options

        self.errors = [
            "Did not login correctly (err: -1)",
            "Received unexpected password prompt (err: -2)",
            "Could not resolve host (err: -3)",
            "Permission denied (err: -4)",
            "Password denied (err: -5)",
            "Shell prompt guessing failure (err: -6)",
        ]

        if sys.version_info > (3,):
            self.unicode_chr = chr
        else:
            self.unicode_chr = unichr

        self.progress = None
        self.sshc = None
        self.commands = None
        self.commands_on_servers = None

        if not self.options["windows_line_endings"] and \
          not self.options["unix_line_endings"] and hasattr(os, "uname") and \
          "darwin" in os.uname()[0].lower():
            # Apples have special needs... default them to unix line endings
            self.options["unix_line_endings"] = True

        super(Bladerunner, self).__init__()

    def run(self, commands=None, servers=None, commands_on_servers=None):
        """Executes commands on servers.

        Args::

            commands: a list of strings of commands to run
            servers: a list of strings of hostnames
            commands_on_servers: an optional dictionary used when providing
                                 unique lists of commands per server

        Returns:
            a list of dictionaries with two keys: name, and results. results
            is a list of tuples of commands issued and their replies.
        """

        if not isinstance(servers, list):
            servers = [servers]

        if not isinstance(commands, list):
            commands = [commands]

        servers = self._prep_servers(commands, servers, commands_on_servers)

        if self.options["progressbar"]:
            self.progress = ProgressBar(len(servers), self.options)
            self.progress.setup()

        if self.options["jump_host"]:
            jumpuser = self.options["jump_user"] or self.options["username"]
            (self.sshc, error_code) = self.connect(
                self.options["jump_host"],
                jumpuser,
                self.options["jump_pass"],
                self.options["jump_port"],
            )
            if error_code < 0:
                message = int(math.fabs(error_code)) - 1
                raise SystemExit("Jumpbox Error: {0}".format(
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

    def _run_thread(self, commands, servers, commands_on_servers, callback):
        """Wrapper function to execute self.run with a callback."""

        results = self.run(commands, servers, commands_on_servers)

        if callback:
            callback(results)

    def run_threaded(self, commands=None, servers=None,
                     commands_on_servers=None, callback=None):
        """Non-blocking call which creates and starts a thread for self.run().

        Args::

            commands: a list of strings of commands to run
            servers: a list of strings of hostnames
            commands_on_servers: an optional dictionary used when providing
                                 unique lists of commands per server
            callback: function that will receive results when run is finished

        Returns:
            the started thread object which is running commands on servers
        """

        thread = threading.Thread(
            target=self._run_thread,
            args=(commands, servers, commands_on_servers, callback),
        )
        thread.start()
        return thread

    def _prep_servers(self, commands, servers, commands_on_servers=None):
        """Checks to see if any of the servers passed are CIDR-ish networks.

        Args::

            commands: list of commands to run
            servers: list of servers to run the commands on
            commands_on_servers: dictionary mapping commands to servers

        Returns:
            list of servers to run on, including any expanded networks
        """

        if commands_on_servers is not None:
            for server, command_list in commands_on_servers.items():
                if not isinstance(command_list, list):
                    command_list = [command_list]

                network_members = ips_in_subnet(server)
                if network_members:
                    commands_on_servers.pop(server)
                    for member in network_members:
                        commands_on_servers[member] = command_list
                else:
                    commands_on_servers[server] = command_list

            expanded_servers = commands_on_servers.keys()
            commands = None
        else:
            expanded_servers = []
            for server in servers:
                network_members = ips_in_subnet(server)
                if network_members:
                    expanded_servers.extend(network_members)
                else:
                    expanded_servers.append(server)

        self.commands = commands
        self.commands_on_servers = commands_on_servers

        return expanded_servers

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
            if self.options["unix_line_endings"]:
                server.send("{0}{1}".format(
                    command,
                    self.unicode_chr(0x000A),
                ))
            elif self.options["windows_line_endings"]:
                server.send("{0}{1}{2}".format(
                    command,
                    self.unicode_chr(0x000D),
                    self.unicode_chr(0x000A),
                ))
            else:
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
            ) and len(self.options["second_password"] or "") > 0:
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

        try:
            # prompt is usually in the last 30 chars of the last line of output
            new_prompt = format_line(output.splitlines()[-1][-30:])
        except IndexError:
            # blank last line could cause an IndexError, should send a newline
            pass
        else:
            # escape regex characters
            replacements = ["\\", "/", ")", "(", "[", "]", "{", "}", " ", "$",
                            "?", ">", "<", "^", ".", "*"]
            for char in replacements:
                new_prompt = new_prompt.replace(char, "\{0}".format(char))

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

        if self.commands_on_servers:
            commands = self.commands_on_servers[hostname]
        else:
            commands = self.commands

        for command in commands:
            command_result = self._send_cmd(command, server)
            if not command_result or command_result == "\n":
                command_results.append((
                    command,
                    "no output from: {0}".format(command),
                ))
            elif command_result == -1:
                command_results.append((
                    command,
                    "did not return after issuing: {0}".format(command),
                ))
            else:
                command_results.append((command, command_result))

        results["results"] = command_results
        return results

    def _build_ssh_command(self, target, username, port):
        """Builds the ssh connection command.

        Args::

            target: string hostname to connect to
            username: string username to connect as
            port: integer port number to use

        Returns:
            string ssh command with valid option flags
        """

        # default flags
        flags = ["-p", str(port), "-t"]

        if self.options["ssh_key"] and os.path.isfile(self.options["ssh_key"]):
            flags.extend(["-i", self.options["ssh_key"]])

        debug = self.options["debug"]
        if isinstance(debug, int) and debug > 0:
            flags.append("-{0}".format("v" * debug))

        return "ssh {flags} {user}@{host}".format(
            flags = " ".join(flags),
            user=username,
            host=target,
        )

    def connect(self, target, username, password, port):
        """Connects to a server, maybe from another server.

        Args::

            target: the hostname, as a string
            username: the user we are connecting as
            password: list or string plain text password(s) to try
            port: ssh port number, as integer

        Returns:
            a pexpect object that can be passed back here or to send_commands()
        """

        if not can_resolve(target):
            return (None, -3)

        ssh_cmd = self._build_ssh_command(target, username, port)

        if not self.sshc:
            try:
                sshr = pexpect.spawn(ssh_cmd)

                if self.options["debug"]:
                    sshr.logfile_read = sys.stdout

                login_response = sshr.expect(
                    self.options["passwd_prompts"] +
                    self.options["shell_prompts"] +
                    self.options["extra_prompts"],
                    self.options["timeout"],
                )

                if self.options["jump_host"]:
                    self.sshc = sshr

                return self._multipass(sshr, password, login_response)
            except (pexpect.TIMEOUT, pexpect.EOF):
                return (None, -1)
        else:
            self.sshc.sendline(ssh_cmd)

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

            return self._multipass(self.sshc, password, login_response)

    def _multipass(self, sshc, passwords, login_response):
        """Buffer to use multiple passwords if using a list of passwords.

        Args::

            sshc: the pexpect object
            passwords: list or string of passwords to try
            login_response: the pexpect return status integer

        Returns:
            a tuple of the pexpect object and error code, tries to be positive
        """

        if not hasattr(passwords, "__iter__"):
            passwords = [passwords]

        error_code = -1
        for password in passwords:
            sshc_returned, error_code = self.login(sshc, password,
                login_response)
            if sshc_returned and error_code > 0:
                return (sshc_returned, error_code)
        else:
            return (None, error_code)

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
            sshc.sendline(self.unicode_chr(0x003))
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


def _set_shells(options):
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

    shells.append("\\[{0}@.*\\]\\$".format(options["username"]))
    shells.append("{0}@.*:~\\$".format(options["username"]))
    password_shells.append("{0}@.*assword\\:".format(options["username"]))
    password_shells.append("{0}\\:".format(options["username"]))

    if options["jump_user"]:
        shells.append("\\[{0}@.*\\]\\$".format(options["jump_user"]))
        shells.append("{0}@.*:~\\$".format(options["jump_user"]))
        password_shells.append("{0}@.*assword:".format(options["jump_user"]))
        password_shells.append("{0}:".format(options["jump_user"]))

    options["shell_prompts"] = shells
    options["passwd_prompts"] = password_shells

    if not isinstance(options["extra_prompts"], list):
        options["extra_prompts"] = [options["extra_prompts"]]

    return options
