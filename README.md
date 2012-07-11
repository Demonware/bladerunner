bladerunner
=================================

Backstory
---------

bladerunner is intended to be a simple way to run a command or list of 
commands in sequence across a multitude of hosts and group the
output in an easy to read fashion. bladerunner is formerly known as clcout,
Clustered Command Output.

Install
-------

Get the latest version of bladerunner by issuing:

	git clone https://github.com/a-tal/bladerunner.git

Or update by going into the directory and running:
	
	git pull

The install process is very simple on most distros:

- Install python and python-pexpect.
- ln -s bladerunner/bladerunner.py ~/bin/bladerunner
- Run "bladerunner [OPTIONS] [COMMAND] [HOST...]"

Usage Tips
----------

You can use the following options with bladerunner:

	-f --filename			Load commands from a file
	-h --help				Display the help screen
	-j --jumpbox			Specify the jumpbox hostname
	-k --keyfile			Use a non-default ssh key
	-m --match				Match a specific shell prompt
	-n --no-password		No password prompt
	-p --password			Supply the password on the command line
	-P --jumpbox-password	Use a different password for the jumpbox
	-s --second-password	Second password
	-t --time-delay			Add a time delay between hosts
	-u --username			Use a different user name to connect
	-U --jumpbox-username	Use a different username for the jumpbox
	-v --verbose			Verbose output
	  

Tip: Using a file with a list of commands in it is an easy way to execute complex 
tasks on a multitude of remote hosts. Further explaination available [on the wiki](https://github.com/a-tal/bladerunner/wiki/Switches).

Bugs & TODO
-----------

If you come across bugs feel free to report them via email or edit [the wiki bug page](https://github.com/a-tal/bladerunner/wiki/Bugs).
Also see the wiki for the full list of [things to do](https://github.com/a-tal/bladerunner/wiki/Things-to-do), such as the [various scenarios](https://github.com/a-tal/bladerunner/wiki/Scenarios) with jumpboxes that haven't all been tested.

Feedback/criticism is welcomed, this is my first python project and have only been using the language for a month or two.

Copyright and License
---------------------

bladerunner is copyright 2012 by Adam Talsma <adam@talsma.ca>.

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
