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

if (len(sys.argv) < 2):
	help(False)

sys.argv.pop(0) # first argv is self... trash it
command = sys.argv.pop(0)
userName = getpass.getuser()
sendPassword, verbose, fileName, keyFile, timeDelay, timeLoops, results, finalResults = True, False, '', '', 0, 0, {}, {}
shellPrompts = [ '\[' + userName + '\@.*\]', \
		 userName + '\@.*\:\~\$', \
		 userName + '\@.*\:\~\#', \
		 'mysql\>', 'ftp\>', 'telnet\>' ]

while command[0] == '-': # switch was passed
	if command[1] == 'v':
		verbose = True
	elif command[1] == 'n':
		sendPassword = False
	elif command[1] == 't':
		try:
			timeDelay = int(sys.argv.pop(0))
		except:
			help(False)
	elif command[1] == 'u':
		try:
			userName = sys.argv.pop(0)
		except:
			help(False)
	elif command[1] == 'f':
		try:
			fileName = sys.argv.pop(0) 
		except:
			help(False)
	elif command[1] == 'm':
		try:
			shellPrompts = sys.argv.pop(0)
		except:
			help(False)
	elif command[1] == 'k':
		try:
			keyFile = sys.argv.pop(0)
		except:
			help(False)
	else:
		help(True)
	try:
		command = sys.argv.pop(0)
	except:
		help(False)

if fileName != '': # if we're loading commands from a file, put what is in "command"
	sys.argv.insert(0,command) # back into the list of potential servers

ips = []
for x in sys.argv:
	if isIP(x): # search for IP addresses
		ips.append(x)
	else:
		dns = canFind(x)
		if dns != False and isIP(dns) == True: # or names that resolve to IPs
			ips.append(x) # this bugs me... doing two dns lookups per server  :|

if (len(ips) == 0):
	help(False)

if sendPassword == True:
	myPass = getpass.getpass("Password: ")
	sendPassword = len(myPass) > 0

for server in ips:
	# Wait around for a while if we've been told to
	if timeDelay > 0 and timeLoops > 0:
		time.sleep(timeDelay)
	
	# Spawn the SSH connection
	if keyFile != '' and os.path.isfile(keyFile):
		sshc = pexpect.spawn('ssh -i ' + keyFile + ' ' + userName + "@" + server)
	else:
		sshc = pexpect.spawn('ssh ' + userName + "@" + server)
	
	if sendPassword == True:
		# Expect a password prompt, if we're supposed to.
		try:
			passwordPrompts = [userName + '\@.*assword:', 'assword:']
			if keyFile != '': passwordPrompts.append("\'" + keyFile + "\':")
			sshc.expect(passwordPrompts, 10)
			if verbose == True: sys.stdout.write(sshc.before + sshc.after)
		except:
			results[server] = 'clcout did not recieve a password prompt, aborting.\n'
			sshc.terminate()
			continue
		# Send the password, expect a shell prompt.
		sshc.sendline(myPass)

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
			sshc.sendline(line)
			try:
				sshc.expect(shellPrompts, 20)
				if verbose == True: sys.stdout.write(sshc.before + sshc.after)
				multiOutput += formatOutput(sshc.before, line)
			except:
				multiOutput = 'clcout did not return after issuing the command.\n'
		results[server] = multiOutput
	else:
		sshc.sendline(command)
		try:
			sshc.expect(shellPrompts, 20)
			if verbose == True: sys.stdout.write(sshc.before + sshc.after)
			results[server] = formatOutput(sshc.before, command)
		except:
			results[server] = 'clcout did not return after issuing the command.\n'
	
	# Close the SSH connection...
	sshc.sendline('exit')
	sshc.terminate()

	timeLoops += 1

# Makes a list of servers and replies, consolodates dupes
for server, reply in results.iteritems():
	found = False
	for repl, serv in finalResults.iteritems():
		if (repl.find(reply) >= 0):
			serv.append(server)
			found = True 
	if found == False:
		finalResults[reply] = [server]

# Prints results
if verbose == False:
	for result, servers in finalResults.iteritems():
		print ' '.join(servers) + " returned:"
		sys.stdout.write(result)
else:
	print ''

sys.exit(0)
