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
	print >>sys.stderr, "Missing pexpect. Try apt-get install python-pexpect"
	sys.exit(1)

def help(verboseHelp):
	print "Usage: clcout [OPTIONS] COMMAND [HOST ...]"
	if verboseHelp == True:
		print "Options:"
		print "  -f <filename>\t\tLoad commands from a file"
		print "  -h \t\t\tThis help screen"
		print "  -t <seconds>\t\tAdd a time delay between hosts"
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
shellPrompts = ['\[' + userName + '\@.*\]', userName + '\@.*\:\~\$', userName + '\@.*\:\~\#']
verbose, fileName, timeDelay, timeLoops = False, '', 0, 0

while command[0] == '-': # switch was passed
	if command[1] == 'v':
		verbose = True
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
results = {}
for server in ips:
	# Wait around for a while if we've been told to
	if timeDelay > 0 and timeLoops > 0:
		time.sleep(timeDelay)
	
	# Spawn the SSH connection
	sshc = pexpect.spawn('ssh ' + userName + "@" + server)
	
	# Expect the password prompt. TODO: add in ssh key first time auth question/response
	try:
		sshc.expect(userName + '@.*assword:')
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
			print >>sys.stderr, "Could not open file: " + fileName
			sys.exit(1)
		multiOutput = ''
		for line in myFile:
			line = line.strip()
			sshc.sendline(line)
			sshc.expect(shellPrompts)
			if verbose == True: sys.stdout.write(sshc.before + sshc.after)
			multiOutput += formatOutput(sshc.before, line)
		results[server] = multiOutput
	else:
		sshc.sendline(command)
		sshc.expect(shellPrompts)
		if verbose == True: sys.stdout.write(sshc.before + sshc.after)
		results[server] = formatOutput(sshc.before, command)
	
	# Close the SSH connection...
	sshc.sendline('exit')
	sshc.terminate()

	timeLoops += 1

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
