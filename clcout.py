#!/usr/bin/env python

# Clustered Command Output, written in Python.
# (c)2012 - Adam Talsma <adam@talsma.ca>.
# Released under the GPL, version 3: http://www.gnu.org/licenses/

# Requires: python-pexpect

from getpass import getpass
import sys
import socket

try:
	import pexpect
except:
	print >>sys.stderr, "Missing pexpect. Try apt-get install python-pexpect"
	sys.exit(1)

def help():
	print "Usage: clcout COMMAND [HOST ...]"
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
	foundOne = False
	for c in letters:
		if c.isalpha() == True:
			foundOne = True
			break
	return foundOne

if (len(sys.argv) < 2):
	help()

sys.argv.pop(0) # first argv is self... trash it
command = sys.argv.pop(0) # command to issue
ips = []

for x in sys.argv:
	if isIP(x): # search for IP addresses
		ips.append(x)
	else:
		dns = canFind(x)
		if dns != False and isIP(dns) == True: # or names that resolve to IPs
			ips.append(x) # this bugs me... doing two dns lookups per server
				      # but you know, it looks prettier at the end... :|

if (len(ips) == 0):
	help()

myPass = getpass("Password: ")
shellPrompts = ['\[.*\@.*\]','.*\@.*:~\$']
#unicode('\x5B.*\@.*\x5D') # unicode prompt, not sure how to mix types here
results = {}
for server in ips:
	sshc = pexpect.spawn('ssh ' + server)
	sshc.expect('.*\@.*assword:') # password prompt. TODO: add in ssh key first time auth
	sshc.sendline(myPass)
	sshc.expect(shellPrompts)
	sshc.sendline(command)
	st = sshc.expect(shellPrompts)
	if st == 0:
		output = sshc.before
	elif st == 1: # ubuntu/centos switch hack
		output = sshc.after	
	output = output.split('\r\n') # tty connections use windows line-endings, because of reasons
	output.pop(-1) # last entry is trash (probably only in centos-untested)
	formattedOutput = ""
	for line in output:
		if (line.find(command) < 0 and tharBeLettersHere(line) == True and line.find('\[.*\@.*\]') < 0):
			formattedOutput += line + "\n"
	results[server] = formattedOutput # append to the dictionary
	sshc.sendline('exit')
	sshc.terminate()

finalResults = {}
for server, reply in results.iteritems():
	found = False
	for repl, serv in finalResults.iteritems():
		if (repl.find(reply) >= 0):
			serv.append(server)
			found = True # makes a list of servers and replies, gets rid of dupes
	if found == False:
		finalResults[reply] = [server]

for result, servers in finalResults.iteritems():
	print ' '.join(servers) + " returned:"
	sys.stdout.write(result)

