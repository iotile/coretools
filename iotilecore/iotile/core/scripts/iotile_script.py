# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

import sys
import os
import shlex

from iotile.core.utilities.typedargs.shell import HierarchicalShell, posix_lex
from iotile.core.exceptions import *
from iotile.core.utilities.typedargs import annotate, type_system
from iotile.core.utilities.rcfile import RCFile
from iotile.core.dev.registry import ComponentRegistry
import iotile.core.hw.transport.cmdstream as cmdstream

from multiprocessing import freeze_support
import traceback

def main():
    type_system.interactive = True
    line = sys.argv[1:]

    norc=False
    if len(line) > 0 and line[0] == '--norc':
        norc = True
        line = line[1:]

    if len(line) > 0 and line[0] == '--rcfile':
        rc = RCFile('iotile')
        print rc.path
        return 0

    shell = HierarchicalShell('iotile', no_rc=norc)
        
    shell.root_add("registry", "iotile.core.dev.annotated_registry,registry")
    shell.root_add('hw', "iotile.core.hw.hwmanager,HardwareManager")

    reg = ComponentRegistry()
    plugins = reg.list_plugins()
    for k,v in plugins.iteritems():
        shell.root_add(k, v)

    finished = False

    try:
        while len(line) > 0:
            line, finished = shell.invoke(line)
    except APIError:
        traceback.print_exc()
        return 1
    except IOTileException as e:
        print e.format()
        #if the command passed on the command line fails, then we should
        #just exit rather than drop the user into a shell.
        return 1

    #Setup file path and function name completion
    #Handle special case of importing pyreadline on Windows
    #See: http://stackoverflow.com/questions/6024952/readline-functionality-on-windows-with-python-2-7
    import glob
    try:
        import readline
    except ImportError:
        import pyreadline as readline

    def complete(text, state):
        buf = readline.get_line_buffer()
        if buf.startswith('help ') or " " not in buf:
            funcs = shell.valid_identifiers()
            return filter(lambda x: x.startswith(text), funcs)[state]

        return (glob.glob(os.path.expanduser(text)+'*')+[None])[state]

    readline.set_completer_delims(' \t\n;')
    #Handle Mac OS X special libedit based readline
    #See: http://stackoverflow.com/questions/7116038/python-tab-completion-mac-osx-10-7-lion
    if readline.__doc__ is not None and 'libedit' in readline.__doc__:
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")

    readline.set_completer(complete)

    #If we ended the initial command with a context, start a shell
    if not finished:
        try:
            while True:
                linebuf = raw_input("(%s) " % shell.context_name())

                # Skip comments automatically
                if len(linebuf) > 0 and linebuf[0] == '#':
                    continue

                line = shlex.split(linebuf, posix=posix_lex)

                #Automatically remove enclosing double quotes on windows since they are not removed by shlex in nonposix mode
                def remove_quotes(x):
                    if len(x) > 0 and x.startswith(("'", '"')) and x[0] == x[-1]:
                        return x[1:-1]

                    return x

                if not posix_lex:
                    line = map(remove_quotes, line)

                #Catch exception outside the loop so we stop invoking submethods if a parent
                #fails because then the context and results would be unpredictable
                try:
                    while len(line) > 0:
                        line, finished = shell.invoke(line)
                except APIError as e:
                    traceback.print_exc()
                except IOTileException as e:
                    print e.format()

                if shell.finished():
                    break

        #Make sure to catch ^C and ^D so that we can cleanly dispose of subprocess resources if 
        #there are any.
        except EOFError:
            print ""
        except KeyboardInterrupt:
            print ""

    #Make sure we close any open CMDStream communication channels so that we don't lockup at exit
    cmdstream.do_final_close()
