bladerunner
=================================

bladerunner is a program to send and receive information from any type of ssh enabled text based device.
It can run through a jumpbox if there are networking restrictions for the execution of the audit. You can 
also provide an additional password to use for any program after logging in, such as MySQL or sudo. MySQL,
ftp, and telnet prompts are included as well as the default Ubuntu and CentOS bash shells and password
prompts. You can provide additional prompts via command line arguments. bladerunner will try to automatically 
accept SSH certificates and will attempt to break out of any command that exceeds the timeout before returning.
Commands can be loaded into a file and run line by line from there, per host.

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
    -U --jumpbox-username=<username>      Use a different user name for the jumpbox (defaults to your system account)
    -m --match=<pattern>                  Match a specific shell prompt
    -n --no-password                      No password prompt
    -r --not-pretty                       Print the uglier, old style output
    -p --password=<password>              Supply the host password on the command line
    -s --second-password=<password>       Use a different second password on the host (-s to prompt)
    -k --ssh-key=<file>                   Use a non-default ssh key
    -t --time-delay=<seconds>             Add a time delay between hosts (default: 0s)
    -u --username=<username>              Use a different user name to connect (defaults to your system account)
    -v --verbose                          Verbose output
    --version                             Displays version information

Tip: Using a file with a list of commands in it is an easy way to execute more complex tasks.

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
