clcout - Clustered Command Output
=================================

Backstory
---------

clcout is intended to be a simple way to run a command or list of 
commands in sequence across a multitude of hosts and group the
output in an easy to read fashion.

Install
-------

The install process is very simple on most distros:

- Install python and python-pexpect.
 ln -s clcout/clcout.py ~/bin/clcout
- Run "clcout [OPTIONS] COMMAND [HOST...]"

Usage Tips
----------

You can use the following options with clcout:
	
	-f <filename>		Import commands from a file
	-j <hostname>		Issue commands from a jumpbox
	-k <keyfile>		Use a non-default ssh key
	-m <pattern>		Match a specific shell prompt
	-n					No password
	-p <password>		Supply the password on the command line
	-s					Second password
	-t <seconds>		Add a time delay between hosts
	-u <username>		Use a different user to SSH
	-v					Prints verbose output

Using a file with a list of commands in it is an easy way to execute complex 
tasks on a multitude of remote hosts.

Bugs & TODO
-----------

If you come across bugs feel free to report them via email or edit [the wiki bug page](https://github.com/a-tal/clcout/wiki/Bugs).
Also see the wiki for the full list of [things to do](https://github.com/a-tal/clcout/wiki/Things-to-do).

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
