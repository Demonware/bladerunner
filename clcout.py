#!/usr/bin/env python

# Clustered Command Output, written in Python.
# (c)2012 - Adam Talsma <adam@talsma.ca>.
# Released under the GPL, version 3: http://www.gnu.org/licenses/

# Requires: python-pexpect

import sys
import socket
import getpass
import os
import time

try:
	import pexpect
except:
	sys.stderr.write("Missing pexpect. Try apt-get install python-pexpect\n")
	sys.exit(1)
	
class clcout:
	def printHelp(self, verboseHelp):
		sys.stdout.write("Usage: clcout [OPTIONS] COMMAND [HOST ...]\n")
		if verboseHelp == True:
			sys.stdout.write("Options:\n")
			sys.stdout.write("  -f <filename>\t\tLoad commands from a file\n")
			sys.stdout.write("  -h \t\t\tThis help screen\n")
			sys.stdout.write("  -k <keyfile>\t\tUse a non-default ssh key\n")
			sys.stdout.write("  -m <pattern>\t\tMatch a specific shell prompt\n")
			sys.stdout.write("  -n \t\t\tNo password prompt\n")
			sys.stdout.write("  -p <password>\t\tSupply the password on the command line\n")
			sys.stdout.write("  -s \t\t\tSecond password\n")
			sys.stdout.write("  -t <seconds>\t\tAdd a time delay between hosts\n")
			sys.stdout.write("  -u <username>\t\tUse a different user name to connect\n")
			sys.stdout.write("  -v \t\t\tVerbose output\n")
			sys.stdout.write("\nJumpbox Options:\n")
			sys.stdout.write("  -j <hostname>\t\tSpecify the jumpbox hostname\n")
			sys.stdout.write("  -i <username>\t\tUse a different username\n")
			sys.stdout.write("  -P \t\t\tPrompt for a different password\n")
			sys.stdout.write("  -S <password>\t\tSupply a different password on the command line\n")
		sys.exit(0)
	
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
	
	def sendCommand(self, sshc, c):
		try:
			sshc.sendline(c)
			if self.sudoPassword:
				sc = sshc.expect(self.shellPrompts + self.passwordPrompts, 20)
				if self.verbose: sys.stdout.write(sshc.before + sshc.after)
				if sc >= len(self.shellPrompts) and len(self.sudoPass) > 0:
					sshc.sendline(self.sudoPass) # sudo password
					sshc.expect(self.shellPrompts, 20)
					if self.verbose: sys.stdout.write(sshc.before + sshc.after)
			else:
				sc = sshc.expect(self.shellPrompts, 20)
				if self.verbose: sys.stdout.write(sshc.before + sshc.after)
			
			return self.formatOutput(sshc, c)
		except:
			return False
	
	def errorQuit(self, error=''):
		sys.stderr.write("%s\n" % error)
		sys.exit(1)
		
	def spawnSshc(self, targetBox):
		# Spawn the SSH connection
		if self.keyFile and os.path.isfile(self.keyFile):
			if self.jumpBoxUser and targetBox == self.jumpBox:
				sshc = pexpect.spawn('ssh -i %s %s@%s' % (self.keyFile, self.jumpBoxUser, targetBox))
			else:
				sshc = pexpect.spawn('ssh -i %s %s@%s' % (self.keyFile, self.userName, targetBox))
		else:
			if self.jumpBoxUser and targetBox == self.jumpBox:
				sshc = pexpect.spawn('ssh %s@%s' % (self.jumpBoxUser, targetBox))
			else:
				sshc = pexpect.spawn('ssh %s@%s' % (self.userName, targetBox))
		return sshc
	
	def runCommands(self, sshc, args):
		if not self.commandFile:
			command = args.pop(0)
		timeLoops, results = 0, {}
		for server in args:
			ipAddress = self.canFind(server)
			if not ipAddress or not self.isIP(ipAddress): 
				results[server] = 'clcout could not resolve %s\n' % server
				continue
			
			# Wait around for a while if we've been told to
			if self.timeDelay > 0 and timeLoops > 0:
				time.sleep(self.timeDelay)
			
			# hop into the next box if we're doing that
			if not self.jumpBox or not sshc or not sshc.isalive():
				sshc = self.spawnSshc(ipAddress)
			else:
				sshc.sendline("ssh %s@%s" % (self.userName, server))
			
			# send a password or expect the next shell prompt
			if self.sendPassword:
				if not self.logIn(sshc, self.myPass): results[server] = 'clcout did not receive a password prompt, aborting.\n'
			else:
				try: 
					sshc.expect(self.shellPrompts, 20)
					if self.verbose: sys.stdout.write(sshc.before + sshc.after)
				except:
					results[server] = 'clcout did not log in properly, aborting.\n'
					continue
		
			# If we're loading commands from a file, do that, otherwise just send the one
			if not self.commandFile:
				results[server] = self.sendCommand(sshc, command) or 'clcout did not return after issuing the command: %s\n' % command
			else:
				multiOutput = ''
				commands = self.openFile(self.commandFile)
				for line in commands:
					line = line.strip(os.linesep)
					lineOutput = self.sendCommand(sshc, line)
					if lineOutput == False:
						multiOutput = 'clcout did not return after issuing the command: %s\n' % line
						break
					multiOutput += lineOutput
				commands.close()
				results[server] = multiOutput
			
			self.closeSshc(sshc, False) if self.jumpBox else self.closeSshc(sshc, True)
			timeLoops += 1
			
		return results, sshc
				
	def logIn(self, sshc, password, st=None):
		try:
			if not st:
				st = sshc.expect(self.passwordPrompts, 20)
				if self.verbose: sys.stdout.write(sshc.before + sshc.after)
	
			if st == 0 and password != 'yes':
				self.logIn(sshc, 'yes', st)
			
			sshc.sendline(password)
			
			if password == 'yes': # recursive logIn function to handle (yes/no)? certificate queries
				self.logIn(sshc, self.myPass)

			sshc.expect(self.shellPrompts, 20)
			if self.verbose: sys.stdout.write(sshc.before + sshc.after)
	
			return True
		except:
			return False
		
	def closeSshc(self, sshc, terminate):
		# Close the SSH connection, expect the jumpbox shell maybe
		sshc.sendline('exit')
		sshc.terminate() if terminate else sshc.expect(self.shellPrompts, 10)
		return True
	
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
	
	def getArgs(self, args):
		try:
			args.pop(0)
			command = args.pop(0)
		except IndexError:
			self.printHelp(False)
		while command[0] == '-': # switch was passed
			for x in range(len(command)):
				if command[x] == '-':
					continue
				
				elif command[x] == 'f':
					try:
						self.commandFile = args.pop(0)
						self.openFile(self.commandFile, True)
					except IndexError:
						self.errorQuit("Missing filename (provided -f)")
						
				elif command[x] == 'h':
					self.printHelp(True)
					
				elif command[x] == 'i':
					try:
						self.jumpBoxUser = args.pop(0)
						self.shellPrompts.append('\[%s\@.*\]' % self.jumpBoxUser)
						self.shellPrompts.append('%s\@.*\:\~\$' % self.jumpBoxUser)
						self.shellPrompts.append('%s\@.*\:\~\#' % self.jumpBoxUser)
					except IndexError:
						self.errorQuit("Missing jumpbox user (provided -i)")
						
				elif command[x] == 'j':
					try:
						self.jumpBox = args.pop(0)
					except IndexError:
						self.errorQuit("Missing jumpbox (provided -j)")
						
				elif command[x] == 'k':
					try:
						self.keyFile = args.pop(0)
						self.passwordPrompts.append("\'%s\':" % self.keyFile)
					except IndexError:
						self.errorQuit("Missing filename (provided -k)")
						
				elif command[x] == 'm':
					try:
						self.shellPrompts.insert(0, args.pop(0))
					except IndexError:
						self.errorQuit("Missing pattern (provided -m)")
						
				elif command[x] == 'n':
					self.sendPassword = False
					
				elif command[x] == 'p':
					try:
						self.myPass = args.pop(0)
					except IndexError:
						self.errorQuit("Missing password (provided -p)")
						
				elif command[x] == 'P':
					self.jumpBoxPassword = True
					
				elif command[x] == 's':
					self.sudoPassword = True
					
				elif command[x] == 'S':
					try:
						self.jumpBoxPassword = args.pop(0)
					except IndexError:
						self.errorQuit("Missing jumpbox password (provided -S)")
						
				elif command[x] == 't':
					try:
						self.timeDelay = int(args.pop(0))
					except IndexError:
						self.errorQuit("Missing seconds (provided -t)")
						
				elif command[x] == 'u':
					try:
						self.userName = args.pop(0)
					except IndexError:
						self.errorQuit("Missing username (provided -u)")
						
				elif command[x] == 'v':
					self.verbose = True
				else:
					self.errorQuit("Unknown option: -%s" % self.command[x])
			
			try:
				command = args.pop(0)
			except IndexError:
				self.printHelp(False)
				
		if (len(args) == 0): 
			self.printHelp(False)
		args.insert(0,command)
		return args
	
	def getPasswords(self):	
		if self.jumpBoxPassword == True and self.jumpBox:
			self.jumpBoxPassword = getpass.getpass("Jumpbox password:")
		
		if self.sendPassword == True and not self.myPass:
			self.myPass = getpass.getpass("Password: ")
		
		self.sendPassword = len(self.myPass) > 0
		
		if self.sudoPassword == True:
			self.sudoPass = getpass.getpass("Second password: ")
		
		if not self.sudoPass:
			self.sudoPass = self.myPass
		
	def getResults(self, args):
		if self.jumpBox:
			ipAddress = self.canFind(self.jumpBox)
			if not ipAddress or not self.isIP(ipAddress):
				self.errorQuit('clcout could not resolve jumpbox: %s' % self.jumpBox)
			
			sshc = self.spawnSshc(self.jumpBox)
			
			if self.jumpBoxPassword:
				if not self.logIn(sshc, self.jumpBoxPassword): self.errorQuit("clcout did not receive a jumpbox password prompt, aborting.")
			elif self.sendPassword:
				if not self.logIn(sshc, self.myPass): self.errorQuit("clcout did not receive a jumpbox password prompt, aborting.")
			
			results, sshc = self.runCommands(sshc, args)
		else:
			results, sshc = self.runCommands(None, args)
		
		self.closeSshc(sshc, True)
		return results
	
	def printResults(self, results):
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
		
		# sys.stdout.write(s results
		if not self.verbose:
			for result, servers in finalResults.iteritems():
				sys.stdout.write(' '.join(servers) + " returned:\n")
				sys.stdout.write(result)
		else:
			sys.stdout.write("\n")
			
		return True
	
	def __init__(self, args):
		self.userName = getpass.getuser()
		self.sendPassword = True
		self.sudoPassword = False
		self.verbose = False
		self.keyFile = ''
		self.commandFile = False
		self.myPass = ''
		self.sudoPass = ''
		self.jumpBox = ''
		self.jumpBoxUser = ''
		self.jumpBoxPassword = False
		self.timeDelay = 0
		self.passwordPrompts = ['(yes/no)\? ', '%s@.*assword:' % self.userName, 'assword:', '%s:' % self.userName]
		self.shellPrompts = ['\[%s\@.*\]' % self.userName, '%s\@.*\:\~\$' % self.userName, '%s\@.*\:\~\#' % self.userName, 'mysql>', 'ftp>', 'telnet>']
		
		args = self.getArgs(args)
		
		try:	
			self.getPasswords()
			if not self.printResults(self.getResults(args)):
				sys.exit(1)
		except KeyboardInterrupt:
			self.errorQuit()

if __name__ == "__main__":
	clcout(sys.argv)
	sys.exit(0)
