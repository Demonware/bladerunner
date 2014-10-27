Bladerunner
=======================================

The Bladerunner codebase is split by function:

.. toctree::
   :maxdepth: 2

   base
   cmdline
   formatting
   interactive
   networking
   progressbar


Use of Bladerunner from within Python
=======================================

It may be useful to run Bladerunner from inside another script. Here's how::

  from bladerunner.base import Bladerunner
  from bladerunner.formatting import csv_results, pretty_results, stacked_results

  def bladerunner_test():
      """A simple test of bladerunner's execution and output formats."""

      # pass in lists of strings, commands and hosts will be executed in order
      servers = ["testserver1.testdomain.com", "testserver2.testdomain.com"]
      commands = ["uptime", "mysql", "show databases;", "exit;", "date"]

      # this is the full options dictionary
      options = {
          "debug": False,
          "delay": None,
          "cmd_timeout": 20,
          "csv_char": ",",
          "extra_prompts": ["core-router1>"],
          "jump_host": "core-router1",
          "jump_password": "cisco",
          "jump_port": 22,
          "jump_user": "admin",
          "output_file": "/home/joebob/Documents/output.txt",
          "passwd_prompts": [],  # usually best to let Bladerunner decide
          "password": "hunter7",
          "password_safety": True,
          "port": 22,
          "progressbar": True,
          "second_password": "super-sekrets",
          "shell_prompts": [],  # this list is typically auto-generated
          "ssh_key": None,
          "stacked": False,  # preference flag for stacked results
          "style": 0,
          "threads": 100,
          "timeout": 20,
          "unix_line_endings": False,
          "username": "joebob",
          "width": 80,  # used in displaying results
          "windows_line_endings": False,  # force the use of \r\n
      }

      # initialize Bladerunner with the options provided
      runner = Bladerunner(options)

      # execution of commands on hosts, may take a while to return
      results = runner.run(commands, servers)

      # Prints CSV results
      csv_results(results)

      # Prints pretty_results using the available styles
      for i in range(4):
          options["style"] = i
          pretty_results(results, options)

      # Prints the results in a flat, vertically stacked way
      stacked_results(results)


Threaded Bladerunner
====================

As of Bladerunner 4.0.0 it is possible to use the run_threaded() method to call the run() method in new thread. This is especially useful inside of Tornado applications, which may need to be responsive in the main thread during a long running task.

It is recommended that you use gen.Task to do this inside of Tornado, but Bladerunner itself simply returns a thread and calls a callback, so it's really up to the implementation as for how the threading is handled. Here's a simple use case for building a non-blocking remote execution function::

  from tornado import gen, web
  from bladerunner.base import Bladerunner

  @gen.engine
  def threaded_commands(options, commands, servers, callback=None):
      runner = Bladerunner(options)
      results = yield gen.Task(runner.run_threaded, commands, servers)
      if callback:
          callback(results)

  class MyHandler(web.RequestHandler):
      @gen.engine
      def get(self, *args, **kwargs):
          commands = self.qs_dict.get("commands", [])
          servers = self.qs_dict.get("servers", [])
          if commands and servers:
              # password can be a list to try multiple passwords per host
              options = {"username": "root", "password": ["r00t", "d3f4ult"]}
              results = yield gen.Task(threaded_commands, options, commands, servers)
              self.write(200, results)
          else:
              self.write(404, "commands or servers not provided in qs_dict")


Bladerunner Interactive
=======================

Sometimes, you need to apply logic to conditionally decide commands to issue based off of the results of a previous command. As of Bladerunner 4.1.0 there are now a couple different ways you can do this.

Single host interactive via python shell
----------------------------------------

Here is the simplest use case of a BladerunnerInteractive object::

  >>> from bladerunner import Bladerunner
  >>> runner = Bladerunner()
  >>> inter = runner.interactive("some_host")
  >>> inter.run("uptime")
  '17:46:22 up 23 days, 19:52,  6 users,  load average: 0.17, 0.13, 0.09'

Multiple hosts interactively via python shell
---------------------------------------------

Rather than handling the BladerunnerInteractive objects yourself, you can store them in the base Bladerunner object instead, letting the base object run the interactive command on all hosts in parallel. An example:

  >>> from bladerunner import Bladerunner
  >>> runner = Bladerunner()
  >>> runner.run_interactive("hostname", "some_host")
  some_host: some_host
  >>> runner.run_interactive("hostname")
  some_host: some_host
  >>> runner.run_interactive("hostname", "some_other_host")
  some_host: some_host
  some_other_host: some_other_host

As you can see, supplying more hosts (the second argument, can also be a list), is optional. If you do supply more hosts, they will be added to the internal list. To remove a host from the pool, use Bladerunner.end_interactive() with the hostname or list of hostnames you'd like to remove::

  >>> runner.end_interactive("some_host")
  >>> runner.interactive_hosts
  {'some_other_host': <bladerunner.interactive.BladerunnerInteractive object at 0xb6f1dd8c>}

Interactive Threading
---------------------

Both the run and the connect methods of the BladerunnerInteractive objects can be threaded. When using the base object's run_interactive method, it will use multi-threading internally to perform the action on all devices in parallel, but the call itself is blocking. To work around this, you need to use the BladerunnerInteractive objects themselves. An example of threaded connecting and threaded interactive command running::

  from tornado import gen
  from bladerunner import Bladerunner

  options = {}
  runner = Bladerunner(options)
  inter = runner.interactive("somewhere")
  connected = yield gen.Task(inter.connect_threaded)
  if connected:
      results = yield gen.Task(inter.run_threaded, "whoami")
      if "root" in results:
          print("god-mode is enabled")
      else:
          print("{} is but a mere plebeian".format(results))
  else:
      print("could not connect")

You do not need to make a specific call to connect_threaded, as the run call will detect that it hasn't connected yet and attempt to. However, it may be preferred to know the connection status earlier.

Predefined Interactive Functions
---------------------------------

In the instance where you know exactly what you're looking for, and exactly what to do based off of that outcome, it may be easiest to write a BladerunnerInteractive function and let the base object do the threading for you. In this way, we can run the same logic against many hosts. An example script where you need to check the running status of a service and issue a restart on any hosts where the service is currently down::

  from bladerunner import Bladerunner

  def my_function(session):
      """You can call this anything, but the signature has to be exact.

      You must accept a single non-keyword argument, which will be the
      BladerunnerInteractive object.

      You can return anything you want, anything other than None will be
      returned grouped as a list with all the other function calls.
      """

      results = session.run("/etc/init.d/httpd status")
      if not "is running..." in results:
          session.run("/etc/init.d/httpd restart")
          return sesssion.server

  def main():
      runner = Bladerunner({"username": "root"})
      res = runner.run_interactive_function(my_function, ["host1", "host2"])
      print("restarted httpd service on: {}".format(", ".join(res)))

  if __name__ == "__main__":
      main()

In the case where you need different connection parameters for multiple sets of devices, make more Bladerunner base objects and spawn the interactive sets off of them. Alternatively, you can call an update on the base object's options, like so::

  from bladerunner import Bladerunner

  def my_function():
      results = session.run("/etc/init.d/httpd status")
      if not "is running..." in results:
          session.run("/etc/init.d/httpd restart")
          return session.server, True
      return session.server, False

  runner = Bladerunner({"username": "user1", "password": "password1"})

  # line separated lists of hostnames or IPs can be passed as string filepaths
  runner.run_interactive_function(my_function, "/root/server_list_1")

  # if you want to end these sessions, remove them from the base object:
  runner.end_interactive("/root/server_list_1")

  # new BladerunnerInteractive objects inherit the base object's settings
  # but you can update them on the base rather than having to make new ones
  runner.options.update({"username": "user2", "password": "password2"})

  # the connections to these servers will be maintained in the base object
  # indefinately! there are also automatic re-connect methods that are used.
  # if you need finer grained control of the sessions, you can pool them
  # externally to enforce timeouts and/or keepalives.
  results = runner.run_interactive_function(my_function, "/root/server_list_2")

  # results at this point is whatever we've defined to return in our function,
  # inside a list with each function run per host (order not guaranteed).
  for server_name, httpd_restarted in results:
      print("httpd on server {} was {}restarted!".format(
          server_name,
          "not " * int(httpd_restarted is False),
      ))


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
