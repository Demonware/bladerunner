#!/usr/bin/env python2.7
# -*- coding: latin-1 -*-

# bladerunner, written in Python.
# (c)2012 - Adam Talsma <atalsma@demonware.net>.
# Released under the GPL version 3: http://www.gnu.org/licenses/

from __future__ import division
import sys
import time
import getpass
import argparse
import os
import socket

try:
    import pexpect
except:
    sys.stderr.write("Missing pexpect. Try apt-get install python-pexpect\n")
    sys.exit(1)

class sshrunner:
    def __init__(self, settings):
        self.settings = settings

    def spawn(self, targetBox, userName, password, sshc=None):
        ipAddress = self.canFind(targetBox)
        if not ipAddress or not self.isIP(ipAddress): 
            return (None, -3)

        if not sshc: # new connection
            if self.settings.keyFile and os.path.isfile(self.settings.keyFile):
                sshc = pexpect.spawn('ssh -i %s %s@%s' % (self.settings.keyFile, userName, targetBox))
            else:
                sshc = pexpect.spawn('ssh %s@%s' % (userName, targetBox))
            try:
                st = sshc.expect((self.settings.passwordPrompts + self.settings.shellPrompts), self.settings.connectionTimeout)
                if self.settings.verbose: sys.stdout.write(sshc.before + sshc.after)
            except:
                return (None, -1)
        else: # ssh inception
            if self.settings.keyFile and os.path.isfile(self.settings.keyFile):
                sshc.sendline('ssh -i %s %s@%s' % (self.settings.keyFile, userName, targetBox))
            else:
                sshc.sendline('ssh %s@%s' % (userName, targetBox))

            try:
                st = sshc.expect((self.settings.passwordPrompts + self.settings.shellPrompts), self.settings.connectionTimeout)
                if self.settings.verbose: sys.stdout.write(sshc.before + sshc.after)
            except:
                self.sendInterrupt(sshc)
                return (None, -1)

            if sshc.before.find('Permission denied') != -1: # pre password denied
                self.sendInterrupt(sshc)
                return (None, -4)

        return self.logIn(sshc, password, st)

    def logIn(self, sshc, password, st):
        if st == 0: # new ssh identity
            sshc.sendline('yes')
            try:
                st = sshc.expect((self.settings.passwordPrompts + self.settings.shellPrompts), self.settings.connectionTimeout)
                if self.settings.verbose: sys.stdout.write(sshc.before + sshc.after)
            except:
                self.sendInterrupt(sshc)
                return (None, -1)

        if st <= len(self.settings.passwordPrompts) and password: # pw prompt as expected
            sshc.sendline(password)
            try:
                sp = sshc.expect((self.settings.shellPrompts + self.settings.passwordPrompts), self.settings.connectionTimeout)
                if self.settings.verbose: sys.stdout.write(sshc.before + sshc.after)
            except: # timeout
                self.sendInterrupt(sshc)
                return (None, -5)
            if sp <= len(self.settings.shellPrompts): # logged in
                return (sshc, 1)
            else: # wrong password/received another passwd prompt
                self.sendInterrupt(sshc)
                return (sshc, -5)

        elif st <= len(self.settings.passwordPrompts) and not password: # pw prompt not expected
            self.sendInterrupt(sshc)
            return (None, -2)
        elif st > len(self.settings.passwordPrompts) and not password: # pwless login as expected
            return (sshc, 1)
        else:
            return (sshc, 1) # logged in without passwd unexpectedly, c'est la vie

    def sendInterrupt(self, sshc): # sends ^c and pushes expect forward
        try:
            sshc.sendline('\003')
            sshc.expect(self.settings.shellPrompts, 3)
            if self.settings.verbose: sys.stdout.write(sshc.before + sshc.after)
        except:
            pass
        try:
            sshc.expect(self.settings.shellPrompts, 2)
            if self.settings.verbose: sys.stdout.write(sshc.before + sshc.after)
        except:
            pass

    def isIP(self, i):
        try:
            socket.inet_aton(i) # asks the socket module if it's a legal address
            return (len(i.split('.')) == 4) # true unless edge case (10.1 is a legal address)
        except socket.error:
            return False

    def canFind(self, name):
        try:
            return(socket.gethostbyname(name))
        except socket.error:
            return False

    def close(self, sshc, terminate):
        try:
            sshc.sendline('exit')
        except:
            pass
        if terminate:
            sshc.terminate()
            return True
        else:
            try:
                sshc.expect(self.settings.shellPrompts, self.settings.connectionTimeout)
                return sshc
            except:
                return False

class commandrunner:
    def __init__(self, settings, srunner):
        self.settings = settings
        self.srunner = srunner

    def formatOutput(self, sshc, command):
        s = sshc.before
        s = s.split('\r\n') # tty connections use windows line-endings, because of reasons
        formattedOutput = ''
        for l in s[1:-1]: # first line is the command, last line is the return to shell prompt
            l = l.strip(os.linesep)
            l = l.replace('\r', '')
            if not self.commandInLine(command, l):
                formattedOutput += "%s\n" % l
        return formattedOutput

    def commandInLine(self, command, l):
        if len(command) < 60: # this only applies to long commands
            return False
        cl = [command[:60], command[-60:]]
        count = 60
        while(1):
            cladd = command[count:(count + 60)]
            if len(cladd) != 60: break
            cl.append(cladd)
            count += 60
        for fraction in cl:
            if l.find(fraction) > -1:
                return True
        return False

    def sendCommand(self, sshc, c, silent=False):
        try:
            sshc.sendline(c)
            sc = sshc.expect(self.settings.shellPrompts + self.settings.passwordPrompts, self.settings.commandTimeout)
            if self.settings.verbose: sys.stdout.write(sshc.before + sshc.after)
            if sc >= len(self.settings.shellPrompts) and len(self.settings.secondPassword) > 0:
                sshc.sendline(self.settings.secondPassword)
                sshc.expect(self.shellPrompts, self.settings.commandTimeout)
                if self.settings.verbose: sys.stdout.write(sshc.before + sshc.after)
        except pexpect.TIMEOUT:
            self.srunner.sendInterrupt(sshc)
            return -1

        if silent: return True

        return self.formatOutput(sshc, c)

    def runCommands(self, sshc, server):
        results = {'':{'':''}}
        if not self.settings.commandFile:
            reply = self.sendCommand(sshc, self.settings.command)
            if not reply or reply == '\n':
                results[server] = {'no output from: %s\n' % self.settings.command : self.settings.command}
            elif reply == -1: 
                results[server] = {'did not return after issuing the command: %s\n' % self.settings.command : self.settings.command}
            else:
                results[server] = {reply : self.settings.command}
        else:
            multiOutput = {}
            for line in self.settings.commandFile:
                lineOutput = self.sendCommand(sshc, line)
                if not lineOutput or lineOutput == '\n':
                    multiOutput['no output from: %s\n' % line] = line
                elif lineOutput == -1:
                    multiOutput['did not return after issuing the command: %s\n' % line] = line
                else:
                    multiOutput[lineOutput] = line
            results[server] = multiOutput
	
        return results

class progressBar:
    def __init__(self, settings):
        self.die = settings.verbose
        if self.die: return
        self.t = len(settings.servers) # total number of updates expected
        self.w = self.getWidth() - ((len(str(self.t)) * 2 ) + 4) # minimum usable blocks wide
        self.s = 0 # update counter

    def setup(self):
        if self.die: return
        sys.stdout.write("[%s] %d/%d" % (" " * (self.w + (len(str(self.t)) - len(str(self.s)))), self.s, self.t))
        sys.stdout.flush()

    def update(self):
        if self.die: return
        self.w = self.getWidth() - ((len(str(self.t)) * 2 ) + 4) # reinit incase term size changes
        self.s += 1
        missingDifference = (len(str(self.t)) - len(str(self.s)))
        blocksFloat = ((self.s / self.t) * (self.w + missingDifference))
        blocksWrote = int(blocksFloat)
        sys.stdout.write("\r[%s" % ("=" * blocksWrote))
        if int((blocksFloat * 100) % 100) > 49:
            sys.stdout.write("-")
            blocksWrote += 1
        sys.stdout.write("%s] %d/%d" % (" " * (self.w + missingDifference - blocksWrote), self.s, self.t))
        sys.stdout.flush()

    def clean(self):
        if self.die: return
        sys.stdout.write("\r%s" % (" " * self.getWidth()))
        sys.stdout.flush()
        sys.stdout.write("\r")
        sys.stdout.flush()

    def getWidth(self): # credit for this function: http://stackoverflow.com/a/566752
        env = os.environ
        def ioctl_GWINSZ(fd):
            try:
                import fcntl, termios, struct
                cr = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
            except:
                return None
            return cr

        cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
        if not cr:
            try:
                fd = os.open(os.ctermid(), os.O_RDONLY)
                cr = ioctl_GWINSZ(fd)
                os.close(fd)
            except:
                pass
        if not cr:
            try:
                cr = (env['LINES'], env['COLUMNS'])
            except:
                cr = (25, 80)
        return int(cr[1])

class bladerunner:
    def __init__(self):
        self.started = False

    def printHelp(self): # override argparses's --help 
        sys.stdout.write("Note: [COMMAND] is only optional when --file/-f is set.")
        sys.stdout.write("\nOptions:\n") # alphabetical order based on long option
        sys.stdout.write("  -c --command-timeout=<seconds>\tShell timeout between commands (default: 20s)\n")
        sys.stdout.write("  -T --connection-timeout=<seconds>\tSpecify the connection timeout (default: 20s)\n")
        sys.stdout.write("  -C --csv\t\t\t\tOutput in CSV format, not grouped by similarity\n")
        sys.stdout.write("  -f --file=<file>\t\t\tLoad commands from a file\n")
        sys.stdout.write("  -h --help\t\t\t\tThis help screen\n")
        sys.stdout.write("  -j --jumpbox=<host>\t\t\tUse a jumpbox to intermediary the targets\n")
        sys.stdout.write("  -P --jumpbox-password=<password>\tUse a different password for the jumpbox (-P to prompt)\n")
        sys.stdout.write("  -U --jumpbox-username=<username>\tUse a different user name for the jumpbox (default: %s)\n" % getpass.getuser())
        sys.stdout.write("  -m --match=<pattern>\t\t\tMatch a specific shell prompt\n")
        sys.stdout.write("  -n --no-password\t\t\tNo password prompt\n")
        sys.stdout.write("  -r --not-pretty\t\t\tPrint the uglier, old style output\n")
        sys.stdout.write("  -p --password=<password>\t\tSupply the host password on the command line\n")
        sys.stdout.write("  -s --second-password=<password>\tUse a different second password on the host (-s to prompt)\n")
        sys.stdout.write("  -k --ssh-key=<file>\t\t\tUse a non-default ssh key\n")
        sys.stdout.write("  -t --time-delay=<seconds>\t\tAdd a time delay between hosts (default: 0s)\n")
        sys.stdout.write("  -u --username=<username>\t\tUse a different user name to connect (default: %s)\n" % getpass.getuser())
        sys.stdout.write("  -v --verbose\t\t\t\tVerbose output\n")
        sys.stdout.write("     --version\t\t\t\tDisplays version information\n")

    def errorQuit(self, error=''):
        if self.started: sys.stdout.write('\n')
        sys.stderr.write("%s\n" % error)
        sys.exit(1)

    def csvResults(self, results, settings):
        if settings.verbose: sys.stdout.write('\n')
        sys.stdout.write('server,command,result,\n')
        for s, r in results.iteritems():
            if not s: continue
            for reply, command in r.iteritems():
                sys.stdout.write('%s,%s,' % (s, command))
                lines = reply.split('\n')
                first = True
                for line in lines:
                    if not line:
                        continue
                    if not first: sys.stdout.write('\n')
                    sys.stdout.write('%s' % line)
                    first = False
                sys.stdout.write(',\n')

    def noEmpties(self, l):
        r = []
        for x in l:
            if not x:
                pass
            else:
                r.append(x)
        return r

    def prettyResults(self, results, settings):
        if settings.verbose: sys.stdout.write('\n')
        pb = progressBar(settings)
        width = settings.printFixed or pb.getWidth()
        max_s_len = 0 
        for s1, r1 in results.iteritems():
            if len(str(s1)) > max_s_len: max_s_len = len(str(s1)) 

        if max_s_len < 6: max_s_len = 6

        if settings.jumpBox:
            sys.stdout.write('┌%s┬%s┬%s┐\n' % ('─' * (max_s_len + 2), '─' * (width - max_s_len - 17 - len(settings.jumpBox)), '─' * (len(settings.jumpBox) + 11)))
            sys.stdout.write('│ Server%s │ Result%s│ Jumpbox: %s │\n' % (' ' * (max_s_len - 6), ' ' * (width - max_s_len - 24 - len(settings.jumpBox)), str(settings.jumpBox)))
        else:
            sys.stdout.write('┌%s┬%s┐\n' % ('─' * (max_s_len + 2), '─' * (width - max_s_len - 5)))
            sys.stdout.write('│ Server%s │ Result%s│\n' % (' ' * (max_s_len - 6), ' ' * (width - max_s_len - 12)))

        finalResults = self.consolidate(results)
        loops = 0
        for r, s in finalResults.iteritems():
            if not s: continue
            r = r.split('\n')
            r = self.noEmpties(r)
            if len(r) > len(s):
                count = len(r)
            else:
                count = len(s)

            if loops == 0 and settings.jumpBox:
                sys.stdout.write('├%s┼%s┴%s┤\n' % ('─' * (max_s_len + 2), '─' * (width - max_s_len - 17 - len(settings.jumpBox)), '─' * (len(settings.jumpBox) + 11)))
            else:
                sys.stdout.write('├%s┼%s┤\n' % ('─' * (max_s_len + 2), '─' * (width - max_s_len - 5)))

            for x in range(count):
                try:
                    sys.stdout.write('│ %s' % s[x])
                    if len(str(s[x])) < max_s_len:
                        sys.stdout.write(' ' * (max_s_len - len(str(s[x]))))
                    sys.stdout.write(' │ ')
                except IndexError:
                    sys.stdout.write('│ %s │ ' % (' ' * max_s_len))

                try:
                    sys.stdout.write(r[x])
                    if len(str(r[x])) > (width - max_s_len - 12):
                        sys.stdout.write('\n')
                    else:
                        sys.stdout.write('%s │\n' % (' ' * (width - max_s_len - 7 - len(str(r[x])))))
                except IndexError:
                    sys.stdout.write('%s │\n' % (' ' * (width - max_s_len - 7)))
            loops += 1

        sys.stdout.write('└%s┴%s┘\n' % ('─' * (max_s_len + 2), '─' * (width - max_s_len - 5)))

    def consolidate(self, results):
        # Makes a list of servers and replies, consolidates dupes
        finalResults = {}
        for server, r in results.iteritems():
            if not server: continue
            try:
                reply = sorted(r, key=r.get)
            except:
                reply = r
            reply = ''.join(reply)
            found = False
            for repl, serv in finalResults.iteritems():
                if (repl.find(reply) >= 0):
                    serv.append(server)
                    found = True 
            if not found:
                finalResults[reply] = [server]

        return finalResults

    def printResults(self, results, settings):
        if settings.verbose: return
        if settings.jumpBox:
            sys.stdout.write('Jumped into all hosts from: %s\n' % settings.jumpBox)

        finalResults = self.consolidate(results)	
        for result, servers in finalResults.iteritems():
            sys.stdout.write(' '.join(servers) + " returned:\n")
            sys.stdout.write(result)

    def finalOutput(self, results, settings):
        if settings.printUgly:
            self.printResults(results, settings)
        elif settings.printCSV:
            self.csvResults(results, settings)
        else:
            self.prettyResults(results, settings)
        sys.exit(0)

    def getPasswords(self, settings):	
        if settings.usePassword == True and not settings.password:
            settings.password = getpass.getpass("Password: ")

        if settings.setSecondPassword and not settings.secondPassword:
            settings.secondPassword = getpass.getpass("Second password: ")
        elif not settings.secondPassword:
            settings.secondPassword = settings.password

        if settings.setJumpboxPass and settings.jumpBox:
            settings.jumpboxPass = getpass.getpass("Jumpbox password: ")
        elif not settings.jumpboxPass:
            settings.jumpboxPass = settings.password

        return settings

    def parse(self, args):
        parser = argparse.ArgumentParser(prog='bladerunner', description='bladerunner -- A simple way to run quick audits or push changes to multiple hosts.', add_help=False, formatter_class=argparse.RawDescriptionHelpFormatter)
        parser.add_argument('--command-timeout', '-c', dest='commandTimeout', metavar="SECONDS", nargs=1, type=int, default=20)
        parser.add_argument('--connection-timeout', '-T', dest='connectionTimeout', metavar="SECONDS", nargs=1, type=int, default=20)
        parser.add_argument('--csv', '-C', dest='printCSV', action='store_true', default=False)
        parser.add_argument('--file', '-f', dest='commandFile', metavar="FILE", nargs=1, default=False)
        parser.add_argument('--fixed', dest='printFixed', action='store_true', default=False, help=argparse.SUPPRESS) # barely useful
        parser.add_argument('--help', '-h', dest='getHelp', action='store_true', default=False)
        parser.add_argument('--jumpbox', '-j', dest='jumpBox', metavar="HOST")
        parser.add_argument('--jumpbox-password', dest='jumpboxPass', metavar="PASSWORD", nargs=1, default=False)
        parser.add_argument('--jumpbox-username', '-U', dest='jumpboxUser', metavar="USER", nargs=1, default=False)
        parser.add_argument('--match', '-m', dest='matchPattern', metavar="PATTERN", nargs=1)
        parser.add_argument('--no-password', '-n', dest='usePassword', action='store_false', default=True)
        parser.add_argument('--not-pretty', '-r', dest='printUgly', action='store_true', default=False)
        parser.add_argument('--password', '-p', dest="password", metavar="PASSWORD", nargs=1)
        parser.add_argument('-P', dest='setJumpboxPass', action='store_true', default=False)
        parser.add_argument('-s', dest='setSecondPassword', action='store_true', default=False)
        parser.add_argument('--second-password', dest='secondPassword', metavar="PASSWORD", nargs=1)
        parser.add_argument('--settings', dest='settingsDebug', action='store_true', default=False, help=argparse.SUPPRESS) # debug switch
        parser.add_argument('--ssh-key', '-k', dest='keyFile', metavar="FILE", nargs=1)
        parser.add_argument('--time-delay', '-t', dest='timeDelay', metavar="SECONDS", nargs=1, type=float, default=0)
        parser.add_argument('--username', '-u', dest='userName', metavar="USER", nargs=1)
        parser.add_argument('--verbose', '-v', dest='verbose', action='store_true', default=False)
        parser.add_argument('--version', action='version', version='%(prog)s, version 2.0 (Released: August 10, 2012)\nCopyright (C) 2012 Adam Talsma <atalsma@demonware.net>\nLicense GPLv3: GNU GPL version 3 <http://gnu.org/licenses/gpl.html>\n\nThis is free software; you are free to change and redistribute it.\nThere is NO WARRANTY, to the extent permitted by law.')
        parser.add_argument(dest='command', metavar="COMMAND", nargs='?')
        parser.add_argument(dest='servers', metavar="HOST", nargs=argparse.REMAINDER)

        settings = parser.parse_args(args)
        return (settings, parser)

    def setShells(self, settings):
        settings.shellPrompts = ['mysql\\>', 'ftp\\>', 'telnet\\>', '\\[root\\@.*\\]\\#', 'root\\@.*\\:\\~\\#']
        settings.passwordPrompts = ['(yes/no)\\\?', 'assword:'] 

        if settings.userName == None:
            settings.userName = getpass.getuser()

        settings.shellPrompts.append('\\[%s@.*\\]\\$' % settings.userName)
        settings.shellPrompts.append('%s@.*:~\\$' % settings.userName)
        settings.passwordPrompts.append('%s@.*assword\\:' % settings.userName)
        settings.passwordPrompts.append('%s\\:' % settings.userName)

        if settings.jumpboxUser:
            settings.shellPrompts.append('\\[%s@.*\\]\\$' % settings.jumpboxUser)
            settings.shellPrompts.append('%s@.*:~\\$' % settings.jumpboxUser)
            settings.passwordPrompts.append('%s@.*assword:' % settings.jumpboxUser)
            settings.passwordPrompts.append('%s:' % settings.jumpboxUser)

        if settings.matchPattern:
            settings.shellPrompts.insert(0, settings.matchPattern[0])
            settings.passwordPrompts.insert(1, settings.matchPattern[0]) # pos 0 is for logIn()

        return settings

    def getSettings(self):
        (settings, parser) = self.parse(sys.argv[1:])

        if settings.getHelp:
            parser.print_usage()
            self.printHelp()
            sys.exit(0)

        if settings.printUgly and settings.printCSV or settings.printFixed and settings.printUgly or settings.printFixed and settings.printCSV:
            parser.print_usage()
            sys.exit(1)

        if settings.printFixed:
            settings.printFixed = 80

        if settings.commandFile:
            settings.servers.insert(0, settings.command)
            settings.command = None

            try:
                f = file(settings.commandFile[0],'r')
            except IOError:
                self.errorQuit("Could not open file: %s" % settings.commandFile[0])

            settings.commandFile = []
            for l in f:
                l = l.strip(os.linesep)
                if l == '':
                    continue
                else:
                    settings.commandFile.append(l)
            f.close()

        if settings.servers == [None] or settings.servers == []:
            parser.print_usage()
            sys.exit(1)

        # I love how argparse returns unicode lists.............
        if settings.commandTimeout != 20:
            settings.commandTimeout = int(settings.commandTimeout[0])
        if settings.connectionTimeout != 20:
            settings.connectionTimeout = int(settings.connectionTimeout[0])
        if settings.timeDelay:
            settings.timeDelay = settings.timeDelay[0]
        if settings.password:
            settings.password = settings.password[0]
        if settings.secondPassword:
            settings.secondPassword = settings.secondPassword[0]
        if settings.jumpboxPass:
            settings.jumpboxPass = settings.jumpboxPass[0]

        settings = self.getPasswords(settings)

        if settings.keyFile != None:
            settings.keyFile = settings.keyFile[0] 
        if settings.userName != None:
            settings.userName = settings.userName[0]
        if settings.jumpboxUser:
            settings.jumpboxUser = settings.jumpboxUser[0]

        settings = self.setShells(settings)
        
        if settings.settingsDebug:
            self.errorQuit(settings)

        return settings

    def mainLogic(self):
        settings = self.getSettings()
        srunner = sshrunner(settings)
        comrunner = commandrunner(settings, srunner)
        progress = progressBar(settings)
        progress.setup()
        self.started = True
        results = {}
        loops = 0
        sshc = None

        if settings.jumpBox:
            (sshc, errorCode) = srunner.spawn(settings.jumpBox, settings.jumpboxUser or settings.userName, settings.jumpboxPass)
            if errorCode == -1:
                self.errorQuit('Did not log into jumpbox correctly')
            elif errorCode == -2:
                self.errorQuit('Received an unexpected password prompt from the jumpbox')
            elif errorCode == -3:
                self.errorQuit('Could not resolve the jumpbox') 
            elif errorCode == -4:
                self.errorQuit('Permission denied on the jumpbox')
            elif errorCode == -5:
                self.errorQuit('Password denied on the jumpbox')

        for server in settings.servers:
            if settings.timeDelay and loops > 0: time.sleep(settings.timeDelay)

            (sshr, errorCode) = srunner.spawn(server, settings.userName, settings.password, sshc)
            if errorCode == -1:
                results[server] = 'Did not login correctly\n'
                progress.update()
                continue
            elif errorCode == -2:
                results[server] = 'Received unexpected password prompt\n'
                progress.update()
                continue
            elif errorCode == -3:
                results[server] = 'Could not resolve host\n'
                progress.update()
                continue
            elif errorCode == -4:
                results[server] = 'Permission denied\n'
                progress.update()
                continue
            elif errorCode == -5:
                results[server] = 'Password denied\n'
                progress.update()
                continue
            elif errorCode == 1:
                results.update(comrunner.runCommands(sshr, server))

                if settings.jumpBox:
                    srunner.close(sshr, False)
                else:
                    srunner.close(sshr, True)

            sshr = None
            progress.update()
            loops += 1

        if settings.jumpBox: srunner.close(sshc, True)

        progress.clean()

        self.finalOutput(results, settings)

if __name__ == "__main__":
    br = bladerunner()
    try:
        br.mainLogic()
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        sys.exit(0)
