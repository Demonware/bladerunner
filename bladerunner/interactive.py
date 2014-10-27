"""For running Bladerunner interactively.

This file is part of Bladerunner.

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

import sys
import math
import threading


class BladerunnerInteractive(object):
    """A class to run a Bladerunner session one command at a time.

    Args::

        bladerunner: a Bladerunner base object to inherit options from
        server: string hostname or IP address to connect to
    """

    def __init__(self, bladerunner, server):
        """Initialize with a bladerunner object and a server name/ip."""

        self.bladerunner = bladerunner
        self.server = server
        self.sshr = False

    def connect(self, status_return=False):
        """Initializes the ssh connection object(s).

        Args:
            status_return: boolean to return a status boolean of login success

        Returns:
            False if no connection could be made
        """

        if self.bladerunner.options["jump_host"]:
            sshc, error = self.bladerunner.connect(
                self.bladerunner.options["jump_host"],
                self.bladerunner.options.get("jump_user") or \
                    self.bladerunner.options["username"],
                self.bladerunner.options.get("jump_password") or \
                    self.bladerunner.options["password"],
                self.bladerunner.options.get("jump_port") or \
                    self.bladerunner.options["port"],
            )
            if error < 0:
                self.log(self.bladerunner.errors[int(math.fabs(error)) - 1])
                return False if status_return else None

            self.bladerunner.sshc = sshc

        sshr, error = self.bladerunner.connect(
            self.server,
            self.bladerunner.options["username"],
            self.bladerunner.options["password"],
            self.bladerunner.options["port"],
        )
        if error < 0:
            self.log(self.bladerunner.errors[int(math.fabs(error)) - 1])
            return False if status_return else None

        self.sshr = sshr
        return True if status_return else None

    def _reconnect(self):
        """Reconnect to a lost session."""

        try:
            self.log("connection to {0} has been lost, reconnecting".format(
                self.server))
            self.end()
            return self.connect(status_return=True)
        except KeyboardInterrupt:
            self.log("cancelled reconnect, ending session")
            self.end()

    def end(self):
        """End the interactive session."""

        if self.sshr in [False, None]:
            # end called before succesful connection was made
            self.sshr = None
            return

        try:
            if self.bladerunner.options["jump_host"]:
                self.bladerunner.close(self.sshr, False)
                self.bladerunner.close(self.bladerunner.sshc, True)
            else:
                self.bladerunner.close(self.sshr, True)
        except OSError as error:
            if error.errno != 5:
                raise

        self.sshr = None  # specifically None here, False means call _connect

    def run(self, command):
        """Run the command on the server.

        Returns:
            string results of the command
        """

        connection = self._login_if_not_already()
        if connection is not True:
            return connection  # we've errored connecting

        try:
            ret = self.bladerunner._send_cmd(command, self.sshr)
        except OSError as error:
            if error.errno == 5:
                if self._reconnect() is True:
                    return self.run(command)
                else:
                    return "connection to {0} was lost".format(self.server)
            else:
                raise

        if ret == -1:
            return "did not return after issuing: {0}".format(command)
        else:
            return str(ret)

    def _login_if_not_already(self):
        """Check if this Interactive object is connected, if not do it.

        Returns:
            True if now connected, or a string error
        """

        if self.sshr is False:
            self.log("establishing connection to {0}".format(self.server))
            try:
                self.connect()
            except KeyboardInterrupt:
                self.end()
                return "connection to {0} was canceled".format(self.server)

        if not self.sshr:
            return "connection to {0} is closed".format(self.server)

        return True

    def _run_thread(self, command, callback):
        """Target method for run_threading to call self.run with a callback."""

        results = self.run(command)
        if callback:
            callback(results)

    def run_threaded(self, command, callback=None):
        """Non-blocking call which creates and starts a thread for self.run().

        Args:
            command: string command to send through the interactive session

        Returns:
            a thread object, may need to initially connect to send the command
        """

        thread = threading.Thread(
            target=self._run_thread,
            args=(command, callback),
        )
        thread.start()
        return thread

    def _connect_thread(self, callback):
        """Target method for connect_threaded to connect to the target host.

        Callback:
            boolean of successful connection to the host
        """

        success = self.connect(status_return=True)
        if callback:
            callback(success)

    def connect_threaded(self, callback=None):
        """Non-blocking call to start a thread for the initial connection.

        Returns:
            a started thread object, running self.connect()
        """

        thread = threading.Thread(
            target=self._connect_thread,
            args=(callback,),
        )
        thread.start()
        return thread

    def log(self, message):
        """Mock "logging", prints to stdout if debug is set."""

        if self.bladerunner.options["debug"]:
            print("DEBUG: {0}".format(message), file=sys.stdout)

    def __enter__(self):
        """Context management for BladerunnerInteractive objects.

        This will attempt to connect if it hasn't already.

        Usage example::

            runner = Bladerunner()
            with runner.interactive("somewhere") as inter:
                inter.run("echo 'some fancy command'")

        Raises:
            IOError if login fails on the server
        """

        connected = self._login_if_not_already()
        if connected is not True:
            raise IOError(connected)

        return self

    def __exit__(self, *args, **kwargs):
        """Context management cleanup. Ends the session."""

        self.end()
