clcout - Clustered Command Output
=================================

Backstory
---------

This is my first Python project and I'm sure there are many bugs.
clcout is a simple way to run a command in sequence across a 
multitude of hosts and group the output in an easy to read fashion.

Install
-------

The install process is very simple on most distros:

- Install python and python-pexpect.
 ln -s clcout/clcout.py ~/bin/clcout
- Run "clcout COMMAND [HOST ...]"

Usage Tips
----------

Almost any command should be possible to issue through good quote
usage and bash knowledge. clcout will silently ignore extra input
passed to it if it does not resolve to an ip.

Bugs & TODO
-----------

Currently there is no handler for accepting a new ssh certificate.
Need to add a file input option for running multiple commands.
Add a logging option to capture all output. The shell prompt pattern
match could be considerably more precise and verbose as well for other
platforms and shell prompts.

Copyright and License
---------------------

clcout is copyright 2012 by Adam Talsma <adam@talsma.ca>.

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
