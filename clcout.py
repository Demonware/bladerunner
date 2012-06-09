#!/usr/bin/env python

# Clustered Command Output, written in Python.
# (c)2012 - Adam Talsma <adam@talsma.ca>.
# Released under the GPL, version 3: http://www.gnu.org/licenses/

# Requires: python-pexpect

import sys
import socket
import getpass
import os
import re

try:
	import pexpect
except:
	print >>sys.stderr, "Missing pexpect. Try apt-get install python-pexpect"
	sys.exit(1)

def help(verboseHelp):
	print "Usage: clcout [OPTIONS] COMMAND [HOST ...]"
	if verboseHelp == True:
		print "Options:"
		print "  -f <filename>\t\tLoad commands from a file"
		print "  -h \t\t\tThis help screen"
		print "  -u <username>\t\tUse a different user name to connect"
		print "  -v\t\t\tVerbose output"
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

def tharBeLettersHere(letters):
	letters = repr(letters) # thanks taurgal from #python@freenode.irc
	foundOne = False
	for c in letters:
		if 65 <= ord(c) <= 90 or 97 <= ord(c) <= 122:
			foundOne = True
			break
	for shell in shellPrompts:
		if re.search(shell, letters) != '':
			return False
	return foundOne

def formatOutput(s, command):
	s = s.split('\r\n') # tty connections use windows line-endings, because of reasons
	formattedOutput = ""
	for line in s:
		line = line.strip(os.linesep)
		if (line.find(command) < 0 and tharBeLettersHere(str(line)) == True):
			formattedOutput += line + "\n"
	return formattedOutput

if (len(sys.argv) < 2):
	help(False)

sys.argv.pop(0) # first argv is self... trash it
command = sys.argv.pop(0)
verbose = False
userName = getpass.getuser()
fileName = ''

while command[0] == '-': # switch was passed
	if command[1] == 'v':
		verbose = True
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
			ips.append(x) # this bugs me... doing two dns lookups per server. but you know, it looks prettier in the end... :|

if (len(ips) == 0):
	help(False)

myPass = getpass.getpass("Password: ")
shellPrompts = ['[' + userName + '@.*]', userName + '@.*:~$', userName + '@.*:~#'] # unicode('\x5B.*\@.*\x5D')
print shellPrompts
results = {}
for server in ips:	
	# Spawn the SSH connection
	sshc = pexpect.spawn('ssh ' + userName + "@" + server)

	# Expect the password prompt. TODO: add in ssh key first time auth question/response
	sshc.expect(userName + '@.*assword:')
	if verbose == True: sys.stdout.write(sshc.before + sshc.after)

	# Send the password, expect a shell prompt.
	sshc.sendline(myPass)
	sshc.expect(shellPrompts)
	if verbose == True: sys.stdout.write(sshc.before + sshc.after)

	# If we're loading commands from a file, do that, otherwise just send the one
	if fileName != '':
		try:
			myFile = open(fileName,'r')
		except:
			print >>sys.stderr, "Could not open file: " + fileName
			sys.exit(1)
		multiOutput = ''
		for line in myFile:
			line = line.strip()
			sshc.sendline(line)
			st = sshc.expect(shellPrompts)
			if verbose == True: sys.stdout.write(sshc.before + sshc.after)
			if st == 0: output = sshc.before # TODO: fix this line
			elif st == 1: output = sshc.after # TODO: fix this line
			multiOutput += formatOutput(output, line)
		results[server] = multiOutput
	else:
		sshc.sendline(command)
		st = sshc.expect(shellPrompts)
		if verbose == True: sys.stdout.write(sshc.before + sshc.after)
		if st == 0: output = sshc.before # TODO: fix this line
		elif st == 1: output = sshc.after # TODO: fix this line
		results[server] = formatOutput(output, command)
	
	# Close the SSH connection...
	sshc.sendline('exit')
	sshc.terminate()

# Makes a list of servers and replies, consolodates dupes
finalResults = {}
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
