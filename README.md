bladerunner
=================================

bladerunner is a quick way to push changes or run audits across a
multitude of devices.

Install
-------

A packaged install is coming soon. For now:

- Install python and python-pexpect.
- ln -s bladerunner/bladerunner.py ~/bin/bladerunner
- Run "bladerunner [OPTIONS] [COMMAND] [HOST...]"

Usage Tips
----------

You can use the following options with bladerunner:

    -c --command-timeout=<seconds>        Shell timeout between commands (default: 20s)
    -T --connection-timeout=<seconds>     Specify the connection timeout (default: 20s)
    -C --csv                              Output in CSV format, not grouped by similarity
    -f --file=<file>                      Load commands from a file
    -h --help                             This help screen
    -j --jumpbox=<host>                   Use a jumpbox to intermediary the targets
    -P --jumpbox-password=<password>      Use a different password for the jumpbox (-P to prompt)
    -U --jumpbox-username=<username>      Use a different user name for the jumpbox (default: adam)
    -m --match=<pattern>                  Match a specific shell prompt
    -n --no-password                      No password prompt
    -r --not-pretty                       Print the uglier, old style output
    -p --password=<password>              Supply the host password on the command line
    -s --second-password=<password>       Use a different second password on the host (-s to prompt)
    -k --ssh-key=<file>                   Use a non-default ssh key
    -t --time-delay=<seconds>             Add a time delay between hosts (default: 0s)
    -u --username=<username>              Use a different user name to connect (default: adam)
    -v --verbose                          Verbose output
    --version                             Displays version information

Tip: Using a file with a list of commands in it is an easy way to execute complex 
tasks on a multitude of remote hosts.

Bugs & TODO
-----------

If you come across bugs feel free to report them via email or edit [the wiki bug page](https://github.com/a-tal/bladerunner/wiki/Bugs).
Also see the wiki for the full list of [things to do](https://github.com/a-tal/bladerunner/wiki/Things-to-do).

Copyright and License
---------------------

bladerunner is copyright 2012 by Adam Talsma <atalsma@demonware.net>.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see the
[GNU licenses page](http://www.gnu.org/licenses/).
