#!/usr/bin/env python

# bladerunner, written in Python.
# (c)2012 - Adam Talsma <atalsma@demonware.net>.
# Released under the GPL, version 3: http://www.gnu.org/licenses/

import sys
import time
import getpass
import getopt
import os
import socket

try:
	import pexpect
except:
	sys.stderr.write("Missing pexpect. Try apt-get install python-pexpect\n")
	sys.exit(1)

class sshrunner:
	def spawn(self, targetBox, userName, password, shellPrompts, passwordPrompts, usePassword, keyFile=False, verbose=False, sshc=None):
		if not sshc:
			# Spawn the SSH connection
			if keyFile and os.path.isfile(keyFile):
				sshc = pexpect.spawn('ssh -i %s %s@%s' % (keyFile, userName, targetBox))
			else:
				sshc = pexpect.spawn('ssh %s@%s' % (userName, targetBox))
		else:
			if keyFile and os.path.isfile(keyFile):
				sshc.sendline('ssh -i %s %s@%s' % (keyFile, userName, targetBox))
			else:
				sshc.sendline('ssh %s@%s' % (userName, targetBox))

		return self.logIn(sshc, password, shellPrompts, passwordPrompts, usePassword, verbose)

	def logIn(self, sshc, password, shellPrompts, passwordPrompts, usePassword, verbose, st=None):
		try:
			if not usePassword:
				sshc.expect(shellPrompts, 20)
				if verbose: sys.stdout.write(sshc.before + sshc.after)
				return sshc

			if not st:
				st = sshc.expect(passwordPrompts, 20)
				if verbose: sys.stdout.write(sshc.before + sshc.after)

			if st == 0 and password != 'yes':
				self.logIn(sshc, 'yes', shellPrompts, passwordPrompts, verbose, st)

			sshc.sendline(password)

			if password == 'yes': # recursive logIn function to handle (yes/no)? certificate queries
				self.logIn(sshc, password, shellPrompts, passwordPrompts, verbose)

			sshc.expect(shellPrompts, 20)
			if verbose: sys.stdout.write(sshc.before + sshc.after)
			return sshc
		except:
			return False

	def close(self, sshc, shellPrompts, terminate):
		sshc.sendline('exit')
		if terminate:
			sshc.terminate()
			return True
		else:
			try:
				sshc.expect(shellPrompts, 20)
				return sshc
			except:
				return False

class commandrunner:
	def isIP(self, i):
		try:
			socket.inet_aton(i) # asks the socket module if it's a legal address
			return (len(i.split('.')) == 4) # checks that it's also in xxx.xxx.xxx.xxx format
		except socket.error:
			return False
	
	def canFind(self, name):
		try:
			return(socket.gethostbyname(name))
		except socket.error:
			return False
	
	def hasLetters(self, letters):
		foundOne = False
		for c in letters:
			if 65 <= ord(c) <= 90 or 97 <= ord(c) <= 122:
				foundOne = True
				break
		return foundOne
	
	def formatOutput(self, sshc, command):
		s = sshc.before
		s = s.split('\r\n') # tty connections use windows line-endings, because of reasons
		s.pop(-1) # last output line is the return to shell prompt
		formattedOutput = ''
		for l in s:
			l = l.strip(os.linesep)
			if (l.find(command) == -1 and self.hasLetters(l)):
				formattedOutput += "%s\n" % l
		return formattedOutput

	def sendCommand(self, sshc, c, commandTimeout, silent=False):
		try:
			sshc.sendline(c)
			if self.sudoPassword:
				sc = sshc.expect(self.shellPrompts + self.passwordPrompts, commandTimeout or 20)
				if self.verbose: sys.stdout.write(sshc.before + sshc.after)
				if sc >= len(self.shellPrompts) and len(self.sudoPass) > 0:
					sshc.sendline(self.sudoPass) # sudo password
					sshc.expect(self.shellPrompts, commandTimeout or 20)
					if self.verbose: sys.stdout.write(sshc.before + sshc.after)
			else:
				sshc.expect(self.shellPrompts, commandTimeout or 20)
				if self.verbose: sys.stdout.write(sshc.before + sshc.after)

			if not silent:
				return self.formatOutput(sshc, c)
		except:
			return False

		return True
	
	def errorQuit(self, error=''):
		sys.stderr.write("%s\n" % error)
		sys.exit(1)
	
	def runCommands(self, sshc, server):
		results = {}
		ipAddress = self.canFind(server)
		if not ipAddress or not self.isIP(ipAddress): 
			results[server] = 'could not resolve %s\n' % server
			return results
		
		# If we're loading commands from a file, do that, otherwise just send the one
		if not self.commandFile:
			results[server] = self.sendCommand(sshc, self.command, self.commandTimeout) or 'did not return after issuing the command: %s\n' % self.command
		else:
			multiOutput = ''
			commands = self.openFile(self.commandFile)
			for line in commands:
				line = line.strip(os.linesep)
				lineOutput = self.sendCommand(sshc, line, self.commandTimeout)
				if lineOutput == False:
					multiOutput = 'did not return after issuing the command: %s\n' % line
					break
				multiOutput += lineOutput
			commands.close()
			results[server] = multiOutput
			
		return results
	
	def openFile(self, fileName, check=False):
		try:
			f = open(fileName,'r')
		except IOError:
			self.errorQuit("Could not open file: %s" % f)
		if check:
			f.close()
			return True
		else:
			return f
	
	def __init__(self, cmd='', fileName='', sshKey='', shellPattern='', passPattern='', usePassword=True, password='', secondPassword=False, timed=0, user='', cTimeout=False, vbose=False):
		self.command = cmd
		self.userName = user
		self.sendPassword = usePassword
		self.sudoPassword = secondPassword
		self.verbose = vbose
		self.keyFile = sshKey
		self.commandFile = fileName
		self.myPass = password
		self.sudoPass = secondPassword
		self.timeDelay = timed
		self.passwordPrompts = passPattern
		self.shellPrompts = shellPattern
		self.commandTimeout = cTimeout
		
class bladerunner:
	def printHelp(self, verboseHelp=False):
		sys.stdout.write("Usage: bladerunner [OPTIONS] COMMAND [HOST ...]\n")
		if verboseHelp == True:
			sys.stdout.write("Options:\n")
			sys.stdout.write("  -f --file=<file>			Load commands from a file\n")
			sys.stdout.write("  -h --help				This help screen\n")
			sys.stdout.write("  -j --jumpbox=<host>			Use a jumpbox to intermediary the targets\n")
			sys.stdout.write("  -k --key=<file>			Use a non-default ssh key\n")
			sys.stdout.write("  -m --match=<pattern>			Match a specific shell prompt\n")
			sys.stdout.write("  -n --no-password			No password prompt\n")
			sys.stdout.write("  -o --command-timeout=<seconds>	Shell timeout between commands (default 20s)\n")
			sys.stdout.write("  -p --password=<password>		Supply the host password on the command line\n")
			sys.stdout.write("  -P --jumpbox-password			Use a different password for the jumpbox\n")
			sys.stdout.write("  -s --second-password			Use a different second password on the host\n")
			sys.stdout.write("  -t --time-delay=<seconds>		Add a time delay between hosts\n")
			sys.stdout.write("  -u --username=<username>		Use a different user name to connect\n")
			sys.stdout.write("  -U --jumpbox-username=<username>	Use a different user name for the jumpbox\n")
			sys.stdout.write("  -v --verbose				Verbose output\n")
		sys.exit(0)
		
	def errorQuit(self, error=''):
		sys.stderr.write("%s\n" % error)
		sys.exit(1)
		
	def printResults(self, results, jumpBox):
		if jumpBox:
			sys.stdout.write('jumped into all hosts from %s\n' % jumpBox)
		
		# Makes a list of servers and replies, consolidates dupes
		finalResults = {}
		for server, reply in results.iteritems():
			found = False
			for repl, serv in finalResults.iteritems():
				if (repl.find(reply) >= 0):
					serv.append(server)
					found = True 
			if not found:
				finalResults[reply] = [server]
		
		for result, servers in finalResults.iteritems():
			sys.stdout.write(' '.join(servers) + " returned:\n")
			sys.stdout.write(result)
			
		return True
	
	def getPasswords(self, usePassword, password, secondPassword, jumpboxPass):	
			if usePassword == True and not password:
				password = getpass.getpass("Password: ")
			
			usePassword = len(password) > 0
			
			if secondPassword == True:
				secondPassword = getpass.getpass("Second password: ")
			elif not secondPassword:
				secondPassword = password
			
			if jumpboxPass == True:
				jumpboxPass = getpass.getpass("Jumpbox password: ")
			elif not jumpboxPass:
				jumpboxPass = password
			
			return password, secondPassword, jumpboxPass

	def mainLogic(self):
		try:
			options, servers = getopt.getopt(sys.argv[1:], "c:f:hj:k:m:no:p:P:st:u:U:v", \
											["command=", "file=", "help", "jumpbox=", "key=", "match=", "no-password", \
											"password=", "jumpbox-password", "jumpbox-username=", "second-password", \
											"time-delay=", "username=", "command-timeout=", "verbose"])
		except:
			self.printHelp()
		
		command = ''
		fileName = False
		keyFile = False
		usePassword = True
		password = ''
		secondPassword = False
		timeDelay = False
		userName = False
		verbose = False
		shellPrompts = ['mysql>', 'ftp>', 'telnet>']
		jumpBox = False
		jumpboxUser = ''
		jumpboxPass = ''
		commandTimeout = False
				
		# TODO: error better
		for opt, arg in options:
			if opt == '-c' or opt == '--command':
				if not arg or fileName: self.printHelp()
				command = arg
			elif opt == '-f' or opt == '--file':
				if not arg or command: self.printHelp()
				fileName = arg
			elif opt == '-h' or opt == '--help':
				self.printHelp(True)
			elif opt == '-j' or opt == '--jumpbox':
				if not arg: self.printHelp()
				jumpBox = arg
			elif opt == '-k' or opt == '--key':
				if not arg: self.printHelp()
				keyFile = arg
			elif opt == '-m' or opt == '--match':
				if not arg: self.printHelp()
				shellPrompts.insert(0, arg)
			elif opt == '-n' or opt == '--no-password':
				usePassword = False
			elif opt == '-o' or opt == '--command-timeout':
				if not arg: self.printHelp()
				commandTimeout = int(arg)
			elif opt == '-p' or opt == '--password':
				if not arg: self.printHelp()
				password = arg
			elif opt == '-P' or opt == '--jumpbox-password':
				jumpboxPass = True
			elif opt == '-s' or opt == '--second-password':
				secondPassword = True
			elif opt == '-t' or opt == '--time-delay':
				if not arg: self.printHelp()
				timeDelay = float(arg)
			elif opt == '-u' or opt == '--username':
				if not arg: self.printHelp()
				userName = arg
			elif opt == '-U' or opt == '--jumpbox-username':
				if not arg: self.printHelp()
				jumpboxUser = arg
			elif opt == '-v' or opt == '--verbose':
				verbose = True

		if not command and not fileName:
			try:
				command = servers.pop(0)
			except IndexError:
				self.printHelp()

		if not userName:
			userName = getpass.getuser()

		shellPrompts.append('\[%s@.*\]\$' % userName)
		shellPrompts.append('\[root@.*\]\#')
		shellPrompts.append('%s@.*:~\$' % userName)
		shellPrompts.append('root@.*:~#')
		passwordPrompts = ['(yes/no)\? ', '%s@.*assword:' % userName, 'assword:', '%s:' % userName]

		if len(servers) > 1 or len(servers) > 0 and fileName or len(servers) > 0 and command:
			password, secondPassword, jumpboxPass = self.getPasswords(usePassword, password, secondPassword, jumpboxPass)
			srunner = sshrunner()
			comrunner = commandrunner(command, fileName, keyFile, shellPrompts, passwordPrompts, usePassword, password, secondPassword, timeDelay, userName, commandTimeout, verbose)
			results = {}
			if jumpBox:
				sshc = srunner.spawn(jumpBox, jumpboxUser or userName, jumpboxPass, shellPrompts, passwordPrompts, usePassword, keyFile, verbose)
				if not sshc: self.errorQuit('did not log into jumpbox correctly')
				for server in servers:
					sshr = srunner.spawn(server, userName, password, shellPrompts, passwordPrompts, usePassword, keyFile, verbose, sshc)
					if not sshr:
						results[server] = 'did not login correctly\n'
						continue
					results.update(comrunner.runCommands(sshr, server))
					if timeDelay: time.sleep(timeDelay)
					srunner.close(sshr, shellPrompts, False)
					sshr = None
				srunner.close(sshc, shellPrompts, True)
			else:
				for server in servers: 
					sshc = srunner.spawn(server, userName, password, shellPrompts, passwordPrompts, usePassword, keyFile, verbose)
					if not sshc: 
						results[server] = 'did not login correctly\n'
						continue
					results.update(comrunner.runCommands(sshc, server))
					if timeDelay: time.sleep(timeDelay)
					srunner.close(sshc, shellPrompts, True)
					sshc = None
			self.printResults(results, jumpBox)
			sys.exit(0)
		else:
			self.printHelp()
			
if __name__ == "__main__":
	br = bladerunner()
	try:
		br.mainLogic()
	except KeyboardInterrupt:
		br.errorQuit()
