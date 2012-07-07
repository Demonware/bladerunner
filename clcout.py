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

def help(verboseHelp):
	print "Usage: clcout [OPTIONS] COMMAND [HOST ...]"
	if verboseHelp == True:
		print "Options:"
		print "  -f <filename>\t\tLoad commands from a file"
		print "  -h \t\t\tThis help screen"
		print "  -j <hostname>\t\tIssue commands from a jumpbox"
		print "  -k <keyfile>\t\tUse a non-default ssh key"
		print "  -m <pattern>\t\tMatch a specific shell prompt"
		print "  -n \t\t\tNo password prompt"
		print "  -p <password>\t\tSupply the password on the command line"
		print "  -s \t\t\tSecond password"
		print "  -t <seconds>\t\tAdd a time delay between hosts"
		print "  -u <username>\t\tUse a different user name to connect"
		print "  -v \t\t\tVerbose output"
	sys.exit(0)

def isIP(i):
	try:
		socket.inet_aton(i) # asks the socket module if it's a legal address
		return (len(i.split('.')) == 4) # checks that it's also in xxx.xxx.xxx.xxx format
	except socket.error:
		return False

def canFind(name):
	try:
		return(socket.gethostbyname(name))
	except socket.error:
		return False

def hasLetters(letters):
	foundOne = False
	for c in letters:
		if 65 <= ord(c) <= 90 or 97 <= ord(c) <= 122:
			foundOne = True
			break
	return foundOne

def formatOutput(s, command):
	s = s.split('\r\n') # tty connections use windows line-endings, because of reasons
	s.pop(-1) # last output line is the return to shell prompt
	formattedOutput = ""
	for line in s:
		line = line.strip(os.linesep)
		if (line.find(command) == -1 and hasLetters(line)):
			formattedOutput += "%s\n" % line
	return formattedOutput or False

def sendCommand(sshc, c):
	try:
		sshc.sendline(c)
		sc = sshc.expect(shellPrompts + passwordPrompts, 20)
		if verbose: sys.stdout.write(sshc.before + sshc.after)
		if sc >= len(shellPrompts) and len(sudoPass) > 0:
			sshc.sendline(sudoPass) # sudo password
			sshc.expect(shellPrompts, 20)
			if verbose: sys.stdout.write(sshc.before + sshc.after)
		return formatOutput(sshc.before, c)
	except:
		return False

def errorQuit(error):
	sys.stderr.write("%s\n" % error)
	sys.exit(1)
	
def spawnSshc(targetBox):
	# Spawn the SSH connection
	if keyFile and os.path.isfile(keyFile):
		sshc = pexpect.spawn('ssh -i %s %s@%s' % (keyFile, userName, targetBox))
	else:
		sshc = pexpect.spawn('ssh %s@%s' % (userName, targetBox))
	return sshc

def runCommands(sshc):
	timeLoops, results = 0, {}
	for server in sys.argv:
		ipAddress = canFind(server)
		if not ipAddress or not isIP(ipAddress): 
			results[server] = 'clcout could not resolve %s\n' % server
			continue
		
		# Wait around for a while if we've been told to
		if timeDelay > 0 and timeLoops > 0:
			time.sleep(timeDelay)
		
		# hop into the next box if we're doing that
		if not jumpBox or not sshc or not sshc.isalive():
			sshc = spawnSshc(ipAddress)
		else:
			sshc.sendline("ssh %s@%s" % (userName, server))
		
		if sendPassword:
			if not logIn(sshc, myPass, None): results[server] = 'clcout did not receive a password prompt, aborting.\n'
		else:
			try: 
				sshc.expect(shellPrompts, 20)
				if verbose: sys.stdout.write(sshc.before + sshc.after)
			except:
				results[server] = 'clcout did not log in properly, aborting.\n'
				continue
	
		# If we're loading commands from a file, do that, otherwise just send the one
		if commandFile:
			multiOutput = ''
			for line in commandFile:
				line = line.strip(os.linesep)
				lineOutput = sendCommand(sshc, line)
				if not lineOutput:
					multiOutput = 'clcout did not return after issuing the command: %s\n' % line
					break
				multiOutput += lineOutput
			results[server] = multiOutput
		else:
			results[server] = sendCommand(sshc, command) or 'clcout did not return after issuing the command: %s\n' % command
		
		closeSshc(sshc, False) if jumpBox else closeSshc(sshc, True)
		timeLoops += 1
		
	return results, sshc
			
def logIn(sshc, password, st):
	try:
		if not st:
			st = sshc.expect(passwordPrompts, 10)
			if verbose: 
				sys.stdout.write(sshc.before + sshc.after)

		if st == 0 and password != 'yes':
			logIn(sshc, 'yes', st)
		
		sshc.sendline(password)
		
		if password == 'yes': # recursive logIn function to handle (yes/no)? certificate queries
			logIn(sshc, myPass, None)
		
		sshc.expect(shellPrompts, 10)
		if verbose: sys.stdout.write(sshc.before + sshc.after)

		return True
	except:
		return False
	
def closeSshc(sshc, terminate):
	# Close the SSH connection, do it again
	sshc.sendline('exit')
	if terminate:
		sshc.terminate()
	else:
		sshc.expect(shellPrompts, 10)
	return True

if (len(sys.argv) < 2): help(False)
sys.argv.pop(0) # first argv is self... trash it
command = sys.argv.pop(0)
userName = getpass.getuser()
sendPassword, sudoPassword, verbose, fileName, keyFile, commandFile, myPass, sudoPass, timeDelay = True, False, False, '', '', '', '', '', 0
passwordPrompts = ['\(yes\/no\)\? ', '%s\@.*assword:' % userName, 'assword:', '%s:' % userName]
shellPrompts = ['\[%s\@.*\]' % userName, '%s\@.*:~\$' % userName, '%s\@.*:~\#' % userName, 'mysql>', 'ftp>', 'telnet>' ]
jumpBox = ''

while command[0] == '-': # switch was passed
	for x in range(len(command)):
		if command[x] == '-':
			continue
		elif command[x] == 'f':
			try:
				fileName = sys.argv.pop(0)
			except IndexError:
				errorQuit("Missing filename (provided -f)")
			try:
				commandFile = open(fileName,'r')
			except IOError:
				errorQuit("Could not open file: %s" % fileName)
		elif command[x] == 'h':
			help(True)
		elif command[x] == 'j':
			try:
				jumpBox = sys.argv.pop(0)
			except IndexError:
				errorQuit("Missing jumpbox (provided -j)")
		elif command[x] == 'k':
			try:
				keyFile = sys.argv.pop(0)
				passwordPrompts.append("\'%s\':" % keyFile)
			except IndexError:
				errorQuit("Missing filename (provided -k)")
		elif command[x] == 'm':
			try:
				shellPrompts.insert(0, sys.argv.pop(0))
			except IndexError:
				errorQuit("Missing pattern (provided -m)")
		elif command[x] == 'n':
			sendPassword = False
		elif command[x] == 'p':
			try:
				myPass = sys.argv.pop(0)
			except IndexError:
				errorQuit("Missing password (provided -p)")
		elif command[x] == 's':
			sudoPassword = True
		elif command[x] == 't':
			try:
				timeDelay = int(sys.argv.pop(0))
			except IndexError:
				errorQuit("Missing seconds (provided -t)")
		elif command[x] == 'u':
			try:
				userName = sys.argv.pop(0)
			except IndexError:
				errorQuit("Missing username (provided -u)")
		elif command[x] == 'v':
			verbose = True
		else:
			errorQuit("Unknown option: -%s" % command[x])
	try:
		command = sys.argv.pop(0)
	except IndexError:
		help(False)

if fileName:
	sys.argv.insert(0,command) # we're not accepting a command via argv in this case 

if (len(sys.argv) == 0):
	help(False) # no hosts to run on
	
if sendPassword == True and not myPass:
	myPass = getpass.getpass("Password: ")

sendPassword = len(myPass) > 0

if sudoPassword == True:
	sudoPass = getpass.getpass("Second password: ")

if not sudoPass: sudoPass = myPass

if jumpBox:
	ipAddress = canFind(jumpBox)
	if not ipAddress or not isIP(ipAddress):
		errorQuit('clcout could not resolve jumpbox: %s' % jumpBox)
	sshc = spawnSshc(jumpBox)
	if sendPassword:
		if not logIn(sshc, myPass, None): errorQuit("clcout did not receive a jumpbox password prompt, aborting.")
	try: 
		sshc.expect(shellPrompts, 10)
		if verbose: sys.stdout.write(sshc.before + sshc.after)
	except:
		errorQuit("clcout did not log into the jumpbox properly, aborting.")
	results, sshc = runCommands(sshc)
else:
	results, sshc = runCommands(None)
	
closeSshc(sshc, True)

# Makes a list of servers and replies, consolidates dupes
finalResults = {}
for server, reply in results.iteritems():
	found = False
	for repl, serv in finalResults.iteritems():
		if (repl.find(reply) >= 0):
			serv.append(server)
			found = True 
	if not found: finalResults[reply] = [server]

# Prints results
if not verbose:
	for result, servers in finalResults.iteritems():
		print ' '.join(servers) + " returned:"
		sys.stdout.write(result)
else:
	print ''

sys.exit(0)
