#!/usr/bin/env python


"""Bladerunner version 2.6. Released December 28, 2012. Written in Python 2.7.

Provides a method of pushing changes or running audits on groups of similar
hosts over SSH using pexpect (http://pexpect.sourceforge.net). Can be extended
to utilize an intermediary host in the event of networking restrictions.

Copyright (c) 2012, Activision Publishing, Inc.
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list
of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this
list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

* Neither the name of the Activision Publishing, Inc. nor the names of its
contributors may be used to endorse or promote products derived from this
software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""


import sys
import os
import re
import time
import socket
import getpass
import math
import pexpect
from cmdline import cmdline_entry
from progressbar import ProgressBar
from progressbar import get_term_width


class Bladerunner:
    """Main logic for the serial execution of commands on hosts.

    Initialized with an options dictionary with some or all of these keys:
        username: string username, or getpass will guess
        password: string plain text password, if required
        ssh_key: string non-default ssh key file location
        delay: integer in seconds to pause between servers
        extra_prompts: list of strings of additional expect prompts
        width: integer terminal width for output, or it uses all
        jump_host: string hostname of intermediary host
        jump_user: alternate username for jump_host
        jump_password: alternate password for jump_host
        second_password: an additional different password for commands
        cmd_timeout: integer in seconds to wait for commands (20)
        timeout: integer in seconds to wait to connect (20)
        style: integer for outputting. Between 0-3 are pretty, or CSV.
        csv_char: string character to use for CSV results
        progressbar: boolean to declare if we want a progress display
    """

    def __init__(self, options=None):
        """Fills in the options dictionary with any missing keys."""

        if not options:
            options = dict()

        keys = ['username', 'jump_user', 'jump_host', 'jump_password', 'delay',
                'password', 'second_password', 'ssh_key', 'width',
                'extra_prompts']

        for key in keys:
            try:
                options[key]
            except KeyError:
                options[key] = None

        for key in ['cmd_timeout', 'timeout']:
            try:
                options[key]
            except KeyError:
                options[key] = 20

        try:
            options['style']
        except KeyError:
            options['style'] = 0

        try:
            options['csv_char']
        except KeyError:
            options['csv_char'] = ','

        try:
            options['progressbar']
        except KeyError:
            options['progressbar'] = False

        options = set_shells(options)

        self.options = options

    def run(self, commands, servers):
        """Executes commands on servers.

        Args:
            commands: a list of strings of commands to run
            servers: a list of strings of hostnames

        Returns:
            a list of dictionaries with two keys: name, and results. results
            is a list of tuples of commands issued and their replies.
        """

        if self.options['progressbar']:
            progress = ProgressBar(len(servers), self.options)
            progress.setup()

        if type(servers) == type(str()):
            servers = [servers]

        if type(commands) == type(str()):
            commands = [commands]

        results = list()
        sshc = None
        error_messages = [
            'Did not login correctly (err: -1)',
            'Received unexpected password prompt (err: -2)',
            'Could not resolve host (err: -3)',
            'Permission denied (err: -4)',
            'Password denied (err: -5)',
            ]

        if self.options['jump_host']:
            jumpuser = self.options['jump_user'] or self.options['username']
            (sshc, error_code) = self.connect(
                self.options['jump_host'],
                jumpuser,
                self.options['jump_password']
                )
            if error_code < 0:
                message = int(math.fabs(error_code)) - 1
                sys.exit("Jumpbox Error: %s" % error_messages[message])

        for server in servers:
            if self.options['delay'] and servers.index(server) > 0:
                time.sleep(self.options['delay'])

            (sshr, error_code) = self.connect(
                server,
                self.options['username'],
                self.options['password'],
                sshc
                )
            if error_code < 0:
                message = int(math.fabs(error_code)) - 1
                results.append({
                    'name': server,
                    'results': [('login', error_messages[message])],
                    })
            else:
                results.append(self.send_commands(commands, sshr, server))
                self.close(sshr, not self.options['jump_host'])
                sshr = None

            if self.options['progressbar']:
                progress.update()

        if self.options['jump_host']:
            self.close(sshc, True)

        if self.options['progressbar']:
            progress.clear()

        return results

    def send_cmd(self, command, server):
        """Internal method to send a single command to the pexpect object.

        Args:
            command: the command to send
            server: the pexpect object to send to

        Returns:
            The formatted output of the command as a string, or -1 on timeout
        """

        try:
            server.sendline(command)
            cmd_response = server.expect(
                self.options['shell_prompts'] +
                self.options['passwd_prompts'],
                self.options['cmd_timeout'],
                )

            if cmd_response >= len(self.options['shell_prompts']) \
            and len(self.options['second_password']) > 0:
                server.sendline(self.options['second_password'])
                server.expect(
                    self.options['shell_prompts'],
                    self.options['cmd_timeout'],
                    )
        except (pexpect.TIMEOUT, pexpect.EOF):
            self.send_interrupt(server)
            return -1

        return format_output(server.before, command)

    def send_commands(self, commands, server, hostname):
        """Executes the commands on a pexpect object.

        Args:
            commands: a list of string commands to issue
            server: the pexpect host object
            hostname: the string hostname of the server

        Returns:
            a dictionary with two keys:
                name: string of the server's hostname
                results: a list of tuples with each command and its result
        """

        results = {'name': hostname}
        command_results = list()
        for command in commands:
            command_result = self.send_cmd(command, server)
            if not command_result or command_result == '\n':
                command_results.append((
                    command,
                    'no output from: %s' % command,
                    ))
            elif command_result == -1:
                command_results.append((
                    command,
                    'did not return after issuing: %s' % command,
                    ))
            else:
                command_results.append((command, command_result))

        results['results'] = command_results
        return results

    def connect(self, target, username, password, sshc=None):
        """Connects to a server, maybe from another server.

        Args:
            target: the hostname, as a string
            username: the user we are connecting as
            password: plain text password to pass
            sshc: an existing pexpect object to spawn inside of

        Returns:
            a pexpect object that can be passed back here or to send_commands()
        """

        try:
            ip_address = socket.gethostbyname(target)
            socket.inet_aton(ip_address)
            assert len(ip_address.split('.')) == 4
        except (socket.error, AssertionError):
            return (None, -3)

        if not sshc:
            try:
                if self.options['ssh_key'] \
                and os.path.isfile(self.options['ssh_key']):
                    sshc = pexpect.spawn('ssh -i %s %s@%s' % (
                        self.options['ssh_key'],
                        username,
                        target,
                        ))
                else:
                    sshc = pexpect.spawn('ssh %s@%s' % (username, target))
                login_response = sshc.expect(
                    self.options['passwd_prompts'] +
                    self.options['shell_prompts'],
                    self.options['timeout'],
                    )
            except (pexpect.TIMEOUT, pexpect.EOF):
                return (None, -1)
        else:
            if self.options['ssh_key'] \
            and os.path.isfile(self.options['ssh_key']):
                sshc.sendline('ssh -i %s %s@%s' % (
                    self.options['ssh_key'],
                    username,
                    target,
                    ))
            else:
                sshc.sendline('ssh %s@%s' % (username, target))

            try:
                login_response = sshc.expect(
                    self.options['passwd_prompts'] +
                    self.options['shell_prompts'],
                    self.options['timeout'],
                    )
            except (pexpect.TIMEOUT, pexpect.EOF):
                self.send_interrupt(sshc)
                return (None, -1)

            if sshc.before.find('Permission denied') != -1:
                self.send_interrupt(sshc)
                return (None, -4)

        return self.login(sshc, password, login_response)

    def login(self, sshc, password, login_response):
        """Internal method for logging in, used by connect.

        Args:
            sshc: the pexpect object
            password: plain text password to send
            login_response: the pexpect return status integer

        Returns:
            a tuple of the connection object and error code
        """

        if login_response == 0:
            # new identity for known_hosts file
            sshc.sendline('yes')
            try:
                login_response = sshc.expect(
                    self.options['passwd_prompts'] +
                    self.options['shell_prompts'],
                    self.options['timeout'],
                    )
            except (pexpect.TIMEOUT, pexpect.EOF):
                self.send_interrupt(sshc)
                return (None, -1)

        if login_response <= len(self.options['passwd_prompts']) and password:
            # password prompt as expected
            sshc.sendline(password)
            try:
                send_response = sshc.expect(
                    self.options['shell_prompts'] +
                    self.options['passwd_prompts'],
                    self.options['timeout'],
                    )
            except (pexpect.TIMEOUT, pexpect.EOF):
                self.send_interrupt(sshc)
                return (None, -5)
            if send_response <= len(self.options['shell_prompts']):
                # logged in properly with a password
                return (sshc, 1)
            else:
                # wrong password, or received another password prompt
                self.send_interrupt(sshc)
                return (sshc, -5)
        elif login_response <= len(self.options['passwd_prompts']) \
        and not password:
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

        if not self.options['jump_host']:
            return
        try:
            sshc.sendline('\003')
            sshc.expect(self.options['shell_prompts'], 3)
        except (pexpect.TIMEOUT, pexpect.EOF):
            pass
        try:
            sshc.expect(self.options['shell_prompts'], 2)
        except (pexpect.TIMEOUT, pexpect.EOF):
            pass

    def close(self, sshc, terminate):
        """Closes a connection object.

        Args:
            sshc: the pexpect object to close
            terminate: a boolean value to terminate all connections or not

        Returns:
            None: the sshc will be at the jumpbox, or the connection is closed
        """

        sshc.sendline('exit')

        if terminate:
            sshc.terminate()
        else:
            try:
                sshc.expect(
                    self.options['shell_prompts'],
                    self.options['timeout'],
                    )
            except (pexpect.TIMEOUT, pexpect.EOF):
                pass


def no_empties(input_list):
    """Searches through a list and tosses empty elements."""

    output_list = list()
    for item in input_list:
        if item:
            output_list.append(item)
    return output_list


def format_output(output, command):
    """Formatting function to strip colours, remove tabs, etc.

    Args:
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

    output = output.split('\r\n')  # TTY connections use CRLF line-endings
    results = list()
    for line in output[1:-1]:
        line = line.strip(os.linesep)  # can't strip new lines enough
        line = line.replace('\r', '')  # no extra carriage returns
        line = re.sub('\033\[[0-9;]+m', '', line)  # no colours
        line = re.sub('\x1b\[[0-9;]+G', '', line)  # no crazy tabs
        line = re.sub('^\s+', '', line)  # no trailing whitespace
        if not cmd_in_line(command, line):
            results.append("%s" % line)
    return '\n'.join(results)


def consolidate(results):
    """Makes a list of servers and replies, consolidates dupes.

    Args:
        results: the results dictionary from Bladerunner.run

    Returns:
        a results dictionary, with a names key instead of name, containing a
        lists of hosts with matching outputs
    """

    finalresults = list()
    for server in results:
        for tempserver in finalresults:
            if not tempserver:
                continue
            if tempserver['results'] == server['results']:
                tempserver['names'].append(server['name'])
                break
        else:
            server['names'] = [server['name']]
            del server['name']
            finalresults.append(server)

    return finalresults


def csv_results(results, options=None):
    """Prints the results consolidated and in a CSV-ish fashion.

    Args:
        results: the results dictionary from Bladerunner.run
        options: dictionary with optional keys:
            csv_char: a character or string to separate with
    """

    try:
        csv_char = options['csv_char']
    except (KeyError, TypeError):
        csv_char = ','

    sys.stdout.write('server,command,result\r\n')
    for server in results:
        for command, command_result in server['results']:
            command_result = '\n'.join(no_empties(command_result.split('\n')))
            sys.stdout.write('%s%s%s%s%s%s%s%s%s%s%s\r\n' % (
                '"' * int(" " in server['name']),
                server['name'],
                '"' * int(" " in server['name']),
                csv_char,
                '"' * int(" " in command),
                command,
                '"' * int(" " in command),
                csv_char,
                '"' * int(" " in command_result),
                command_result,
                '"' * int(" " in command_result),
                ))


def pretty_results(results, options=None):
    """Prints the results in a relatively pretty way.

    Args:
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
            if len(str(server['name'])) > left_len:
                left_len = len(str(server['name']))
        except KeyError:
            # catches passing already consolidated results in
            already_consolidated = True
            for server_name in server['names']:
                if len(server_name) > left_len:
                    left_len = len(server_name)

    if left_len < 6:
        left_len = 6

    # print characters, defined by options['style'] (also in help)
    chars = {
        'topLeft': [u'\u250C', '*', u'\u2554', u'\u256D'],
        'top': [u'\u2500', '-', u'\u2550', u'\u2500'],
        'topRight': [u'\u2510', '*', u'\u2557', u'\u256E'],
        'topDown': [u'\u252C', '+', u'\u2566', u'\u252C'],
        'sideLeft': [u'\u251C', '*', u'\u2560', u'\u251C'],
        'side': [u'\u2502', '|', u'\u2551', u'\u2502'],
        'middle': [u'\u253C', '+', u'\u256C', u'\u253C'],
        'sideRight': [u'\u2524', '*', u'\u2563', u'\u2524'],
        'botLeft': [u'\u2514', '*', u'\u255A', u'\u2570'],
        'bot': [u'\u2500', '-', u'\u2550', u'\u2500'],
        'botRight': [u'\u2518', '*', u'\u255D', u'\u256F'],
        'botUp': [u'\u2534', '+', u'\u2569', u'\u2534'],
        }

    if not options:
        options = dict()

    try:
        assert 3 >= options['style'] >= 0
    except (AssertionError, KeyError):
        options['style'] = 0

    options['left_len'] = left_len
    options['chars'] = chars

    try:
        width = options['width'] or get_term_width()
    except KeyError:
        width = get_term_width()

    options['width'] = width

    pretty_header(options)

    if not already_consolidated:
        results = consolidate(results)

    for result in results:
        _pretty_result(result, options, results)

    sys.stdout.write('%s%s%s%s%s\n' % (
        chars['botLeft'][options['style']],
        chars['bot'][options['style']] * (left_len + 2),
        chars['botUp'][options['style']],
        chars['bot'][options['style']] * (width - left_len - 5),
        chars['botRight'][options['style']],
        ))


def pretty_header(options):
    """Internal function for printing the header of pretty_results.

    Args:
        options: a dictionary with the following keys:
            width: terminal width, already determined in pretty_results
            chars: the character dictionary map, defined in pretty_results
            left_len: the left side length, defined in pretty_results
            jump_host: a string hostname of the jumpbox (if any)
    """

    try:
        jumpboxhost = options['jump_host']
    except KeyError:
        jumpboxhost = None
        options['jump_host'] = None

    if jumpboxhost:
        sys.stdout.write('%s%s%s%s%s%s%s\n' % (
            options['chars']['topLeft'][options['style']],
            options['chars']['top'][options['style']] * (
                options['left_len']
                + 2
                ),
            options['chars']['topDown'][options['style']],
            options['chars']['top'][options['style']] * (
                options['width']
                - options['left_len']
                - 17
                - len(jumpboxhost)
                ),
            options['chars']['topDown'][options['style']],
            options['chars']['top'][options['style']] * (len(jumpboxhost) + 11),
            options['chars']['topRight'][options['style']],
            ))
        sys.stdout.write('%s Server%s %s Result%s %s Jumpbox: %s %s\n' % (
            options['chars']['side'][options['style']],
            ' ' * (options['left_len'] - 6),
            options['chars']['side'][options['style']],
            ' ' * (
                options['width']
                - options['left_len']
                - 25
                - len(jumpboxhost)
                ),
            options['chars']['side'][options['style']],
            str(jumpboxhost),
            options['chars']['side'][options['style']],
            ))
    else:
        sys.stdout.write('%s%s%s%s%s\n' % (
            options['chars']['topLeft'][options['style']],
            options['chars']['top'][options['style']] * (
                options['left_len']
                + 2
                ),
            options['chars']['topDown'][options['style']],
            options['chars']['top'][options['style']] * (
                options['width']
                - options['left_len']
                - 5
                ),
            options['chars']['topRight'][options['style']],
            ))
        sys.stdout.write('%s Server%s %s Result%s %s\n' % (
            options['chars']['side'][options['style']],
            ' ' * (options['left_len'] - 6),
            options['chars']['side'][options['style']],
            ' ' * (options['width'] - options['left_len'] - 13),
            options['chars']['side'][options['style']],
            ))


def _pretty_result(result, options, consolidated_results):
    """Internal function, ran inside of a loop to print super fancy results.

    Args:
        result: the object iterated over in consolidated_results
        options: the options dictionary from pretty_results
        consolidate_results: the output from consolidate
    """

    chars = options['chars']
    left_len = options['left_len']
    width = options['width']

    result_lines = list()
    for command, command_result in result['results']:
        command_split = no_empties(command_result.split('\n'))
        for command_line in command_split:
            result_lines.append(command_line)

    if len(result_lines) > len(result['names']):
        max_length = len(result_lines)
    else:
        max_length = len(result['names'])

    if consolidated_results.index(result) == 0 and options['jump_host']:
        # first split has a bottom up character when using a jumpbox
        sys.stdout.write('%s%s%s%s%s%s%s\n' % (
            chars['sideLeft'][options['style']],
            chars['top'][options['style']] * (left_len + 2),
            chars['middle'][options['style']],
            chars['top'][options['style']] * (
                width
                - left_len
                - 17
                - len(options['jump_host'])
                ),
            chars['botUp'][options['style']],
            chars['top'][options['style']] * (len(options['jump_host']) + 11),
            chars['sideRight'][options['style']],
            ))
    else:
        # typical horizontal split
        sys.stdout.write('%s%s%s%s%s\n' % (
            chars['sideLeft'][options['style']],
            chars['top'][options['style']] * (left_len + 2),
            chars['middle'][options['style']],
            chars['top'][options['style']] * (width - left_len - 5),
            chars['sideRight'][options['style']],
            ))

    for command in range(max_length):
        # print server name or whitespace, mid mark, and leading space
        try:
            sys.stdout.write('%s %s%s %s ' % (
                chars['side'][options['style']],
                result['names'][command],
                ' ' * (left_len - len(str(result['names'][command]))),
                chars['side'][options['style']],
                ))
        except IndexError:
            sys.stdout.write('%s %s %s ' % (
                chars['side'][options['style']],
                ' ' * left_len,
                chars['side'][options['style']],
                ))

        # print result line, or whitespace, and side mark
        try:
            sys.stdout.write("%s%s %s\n" % (
                result_lines[command],
                ' ' * (
                    width
                    - left_len
                    - 7
                    - len(str(result_lines[command]))
                    ),
                chars['side'][options['style']],
                ))
        except IndexError:
            sys.stdout.write('%s %s\n' % (
                ' ' * (width - left_len - 7),
                chars['side'][options['style']],
                ))


def set_shells(options):
    """Set password, shell and extra prompts for the username.

    Args:
        options dictionary with username, jump_user and extra_prompts keys.

    Returns:
        options dictionary with shell_prompts and passwd_prompts keys
    """

    shells = [
        'mysql\\>',
        'ftp\\>',
        'telnet\\>',
        '\\[root\\@.*\\]\\#',
        'root\\@.*\\:\\~\\#'
        ]
    password_shells = ['(yes/no)\\\?', 'assword:']

    if not options['username']:
        options['username'] = getpass.getuser()

    shells.append('\\[%s@.*\\]\\$' % options['username'])
    shells.append('%s@.*:~\\$' % options['username'])
    password_shells.append('%s@.*assword\\:' % options['username'])
    password_shells.append('%s\\:' % options['username'])

    if options['jump_user']:
        shells.append('\\[%s@.*\\]\\$' % options['jump_user'])
        shells.append('%s@.*:~\\$' % options['jump_user'])
        password_shells.append('%s@.*assword:' % options['jump_user'])
        password_shells.append('%s:' % options['jump_user'])

    try:
        if options['extra_prompts']:
            for prompt in options['extra_prompts']:
                shells.insert(0, prompt)
                # position 0 is used in Bladerunner.login
                password_shells.insert(1, prompt)
    except KeyError:
        pass

    options['shell_prompts'] = shells
    options['passwd_prompts'] = password_shells
    return options


def main_exit(results, options):
    """A buffer for selecting the correct output function and exiting.

    Args:
        results: the results dictionary from Bladerunner.run
        options: the options dictionary, uses 'style' key only
    """

    if options['style'] < 0 or options['style'] > 3:
        csv_results(results, options)
    else:
        try:
            pretty_results(results, options)
        except UnicodeEncodeError:
            csv_results(results, options)
    sys.exit(0)


if __name__ == "__main__":
    COMMANDS, SERVERS, OPTIONS = cmdline_entry()
    BLADERUNNER = Bladerunner(OPTIONS)
    try:
        RESULTS = BLADERUNNER.run(COMMANDS, SERVERS)
        main_exit(RESULTS, OPTIONS)
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        sys.exit(0)
