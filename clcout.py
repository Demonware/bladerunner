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
		print "  -k <keyfile>\t\tUse a non-default ssh key"
		print "  -m <pattern>\t\tMatch a specific shell prompt"
		print "  -n \t\t\tNo password prompt"
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
		if (line.find(command) == -1 and hasLetters(line) == True):
			formattedOutput += line + "\n"
	return formattedOutput

def sendCommand(sshc, c):
	sshc.sendline(c)
	try:
		sc = sshc.expect(shellPrompts + passwordPrompts, 20)
		if verbose == True: sys.stdout.write(sshc.before + sshc.after)
		if sc >= len(shellPrompts) and len(sudoPass) > 0:
			sshc.sendline(sudoPass) # sudo/jumpbox password
			sshc.expect(shellPrompts, 20)
			if verbose == True: sys.stdout.write(sshc.before + sshc.after)
		return formatOutput(sshc.before, c)
	except:
		return 'clcout did not return after issuing the command: ' + c + '\n'

if (len(sys.argv) < 2): help(False)
sys.argv.pop(0) # first argv is self... trash it
command = sys.argv.pop(0)
userName = getpass.getuser()
sendPassword, sudoPassword, verbose, fileName, keyFile, myPass, sudoPass, timeDelay = True, False, False, '', '', '', '', 0
passwordPrompts = [userName + '\@.*assword:', 'assword:', userName + ':']
shellPrompts = [ '\[' + userName + '\@.*\]',  userName + '\@.*:~\$',  userName + '\@.*:~\#', 'mysql>', 'ftp>', 'telnet>' ]

while command[0] == '-': # switch was passed
	for x in range(len(command)):
		if command[x] == '-':
			continue
		elif command[x] == 'f':
			try:
				fileName = sys.argv.pop(0)
			except IndexError:
				help(False)
		elif command[x] == 'h':
			help(True)
		elif command[x] == 'k':
			try:
				keyFile = sys.argv.pop(0)
			except IndexError:
				help(False)
		elif command[x] == 'm':
			try:
				shellPrompts.insert(0, sys.argv.pop(0))
			except IndexError:
				help(False)
		elif command[x] == 'n':
			sendPassword = False
		elif command[x] == 's':
			sudoPassword = True
		elif command[x] == 't':
			try:
				timeDelay = int(sys.argv.pop(0))
			except IndexError:
				help(False)
		elif command[x] == 'u':
			try:
				userName = sys.argv.pop(0)
			except IndexError:
				help(False)
		elif command[x] == 'v':
			verbose = True
		else:
			help(False)
	try:
		command = sys.argv.pop(0)
	except IndexError:
		help(False)

if fileName != '': sys.argv.insert(0,command) 
if (len(sys.argv) == 0): help(False)
if sendPassword == True:
	myPass = getpass.getpass("Password: ")
	sendPassword = len(myPass) > 0
if sudoPassword == True: sudoPass = getpass.getpass("Second password: ")
if sudoPass == '': sudoPass = myPass

timeLoops, results = 0, {}
for server in sys.argv:
	ipAddress = canFind(server)
	if ipAddress == False or isIP(ipAddress) == False: 
		results[server] = 'clcout could not resolve ' + server + '\n'
		continue

	# Wait around for a while if we've been told to
	if timeDelay > 0 and timeLoops > 0: time.sleep(timeDelay)
	
	# Spawn the SSH connection
	if keyFile != '' and os.path.isfile(keyFile):
		sshc = pexpect.spawn('ssh -i ' + keyFile + ' ' + userName + "@" + ipAddress)
	else:
		sshc = pexpect.spawn('ssh ' + userName + "@" + ipAddress)
	
	# Expect a password prompt, if we're supposed to.
	if sendPassword == True: 
		try:
			if keyFile != '': passwordPrompts.append("\'" + keyFile + "\':")
			sshc.expect(passwordPrompts, 10)
			if verbose == True: sys.stdout.write(sshc.before + sshc.after)
		except:
			results[server] = 'clcout did not receive a password prompt, aborting.\n'
			sshc.terminate()
			continue
		sshc.sendline(myPass)
		
	# by this time we should have a shell prompt
	try: 
		sshc.expect(shellPrompts, 10)
		if verbose == True: sys.stdout.write(sshc.before + sshc.after)
	except:
		results[server] = 'clcout did not log in properly, aborting.\n'
		sshc.terminate()
		continue

	# If we're loading commands from a file, do that, otherwise just send the one
	if fileName != '': 
		try:
			myFile = open(fileName,'r')
		except:
			sys.stderr.write("Could not open file: " + fileName + "\n")
			sys.exit(1) # this check should probably happen earlier...
		multiOutput = ''
		for line in myFile:
			line = line.strip(os.linesep)
			runCheck = sendCommand(sshc, line)
			multiOutput += runCheck
			if runCheck == 'clcout did not return after issuing the command: ' + line + '\n': break
		results[server] = multiOutput
	else:
		results[server] = sendCommand(sshc, command)
	
	# Close the SSH connection, do it again
	sshc.sendline('exit')
	sshc.terminate()
	timeLoops += 1

# Makes a list of servers and replies, consolidates dupes
finalResults = {}
for server, reply in results.iteritems():
	found = False
	for repl, serv in finalResults.iteritems():
		if (repl.find(reply) >= 0):
			serv.append(server)
			found = True 
	if found == False: finalResults[reply] = [server]

# Prints results
if verbose == False:
	for result, servers in finalResults.iteritems():
		print ' '.join(servers) + " returned:"
		sys.stdout.write(result)
else:
	print ''

sys.exit(0)
