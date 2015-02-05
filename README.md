Bladerunner
===========

Bladerunner is a program to send and receive information from any type of ssh enabled text based device.
It can run through a jumpbox if there are networking restrictions. You can also provide an additional password
to use for any program after logging in, such as MySQL or sudo. bladerunner will attempt to use the host password
for everything unless you specify otherwise, allowing it to default through sudo in simple use cases. MySQL, FTP,
and telnet prompts are included as well as the default Ubuntu and CentOS bash shells and password prompts. You can
provide an additional prompt via command line arguments. bladerunner will automatically accept SSH certificates and
will throw ^C at any command that exceeds the timeout before returning. Commands can be loaded into a file and run
from there line by line per host.


Install
-------

Installation is done via the usual methods:

```sh
$ python setup.py build
$ sudo python setup.py install
```

Alternatively, you can install via pip:

```sh
$ pip install bladerunner
```


Requires
--------

Python (v2.7+), pexpect and [futures 2.1.3](https://pypi.python.org/pypi/futures).


Options
----------

For a full list of options use:

```sh
bladerunner --help
```

Using a file with a list of commands in it is an easy way to execute more complex tasks.


Further Documentation
---------------------

Sphinx autodocs are available [on pythonhosted](http://pythonhosted.org/bladerunner/).


Python 3
--------

Bladerunner fully supports Python 3.


PyPy
----

Bladerunner is also compatable with [PyPy and PyPy3](http://pypy.org/).


Changelog
---------

The full changelog from version 3.7 onward is available [on the wiki](https://github.com/Demonware/bladerunner/wiki/Changelog).


Bugs & TODO
-----------

If you come across a bug, please create a new issue in the [issue tracking system](https://github.com/Demonware/bladerunner/issues) with enough relevant details and it will be dealt with promptly.


Copyright and License
---------------------

bladerunner was written by Adam Talsma <adam@demonware.net>.

Copyright (c) 2014, Activision Publishing, Inc.
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list
of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice, this
list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

* Neither the name of Activision Publishing, Inc. nor the names of its
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
