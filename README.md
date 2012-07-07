clcout - Clustered Command Output
=================================


Untested
---------

You are in the dev branch. The [various scenarios|https://github.com/a-tal/clcout/wiki/Scenarios] with jumpboxes haven't all been tested. 

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

	-f <filename>		Load commands from a file
	-h					This help screen
	-k <keyfile>		Use a non-default ssh key
	-m <pattern>		Match a specific shell prompt
	-n					No password prompt
	-p <password>		Supply the password on the command line
	-s					Second password
	-t <seconds>		Add a time delay between hosts
	-u <username>		Use a different user name to connect
	-v					Verbose output

Jumpbox Options:
	  -j <hostname>         Specify the jumpbox hostname
	  -i <username>         Use a different username
	  -P 	                		Prompt for a different password
	  -S <password>         Supply a different password on the command line

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
