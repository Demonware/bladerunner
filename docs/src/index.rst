Bladerunner
=======================================

The Bladerunner codebase is split by function:

.. toctree::
   :maxdepth: 2

   base
   cmdline
   formatting
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
          "username": "joebob",
          "password": "hunter7",
          "ssh_key": None,
          "debug": False,
          "delay": None,
          "extra_prompts": ["core-router1>"],
          "width": 80,
          "jump_host": "core-router1",
          "jump_user": "admin",
          "jump_password": "cisco",
          "jump_port": 22,
          "second_password": "super-sekrets",
          "output_file": "/home/joebob/Documents/output.txt",
          "password_safety": True,
          "port": 22,
          "threads": 100,
          "cmd_timeout": 20,
          "timeout": 20,
          "style": 0,
          "unix_line_endings": False,
          "windows_line_endings": False,
          "csv_char": ",",
          "progressbar": True,
          "stacked": False,
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


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
