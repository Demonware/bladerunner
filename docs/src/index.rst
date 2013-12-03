Bladerunner
=======================================

The Bladerunner codebase is split by function:

.. toctree::
   :maxdepth: 2

   bladerunner
   progressbar
   cmdline


Use of Bladerunner from within Python
=======================================

It may be useful to run Bladerunner from inside another script. Here's how::

  from bladerunner import bladerunner

  def bladerunner_test():
      """A simple test of bladerunner's execution and output formats."""

      # pass in lists of strings, commands and hosts will be executed in order
      servers = ['testserver1.testdomain.com', 'testserver2.testdomain.com']
      commands = ['uptime', 'mysql', 'show databases;', 'exit;', 'date']

      # this is the full options dictionary
      options = {
          'username': 'joebob',
          'password': 'hunter7',
          'ssh_key': None,
          'delay': None,
          'extra_prompts': ['core-router1>'],
          'width': 80,
          'jump_host': 'core-router1',
          'jump_user': 'admin',
          'jump_password': 'cisco',
          'jump_port': 22,
          'second_password': 'super-sekrets',
          'output_file': '/home/joebob/Documents/output.txt',
          'password_safety': True,
          'port': 22,
          'threads': 100,
          'cmd_timeout': 20,
          'timeout': 20,
          'style': 0,
          'csv_char': ',',
          'progressbar': True,
      }

      # initialize Bladerunner with the options provided
      blades = bladerunner.Bladerunner(options)

      # execution of commands on hosts, may take a while to return
      results = blades.run(commands, servers)

      # Prints CSV results
      bladerunner.csv_results(results)

      # Prints pretty_results using the available styles
      for i in range(4):
          options['style'] = i
          bladerunner.pretty_results(results, options)


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
