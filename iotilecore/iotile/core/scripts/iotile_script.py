# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import str
import sys
import os
import shlex

from typedargs.shell import HierarchicalShell
from iotile.core.exceptions import *
from typedargs import type_system
from iotile.core.utilities.rcfile import RCFile
from iotile.core.dev.registry import ComponentRegistry
import iotile.core.hw.transport.cmdstream as cmdstream

from multiprocessing import freeze_support
import traceback

def main():
    type_system.interactive = True
    line = sys.argv[1:]

    shell = HierarchicalShell('iotile')

    shell.root_add("registry", "iotile.core.dev.annotated_registry,registry")
    shell.root_add("config", "iotile.core.dev.config,ConfigManager")
    shell.root_add('hw', "iotile.core.hw.hwmanager,HardwareManager")

    reg = ComponentRegistry()
    plugins = reg.list_plugins()
    for k, v in plugins.iteritems():
        shell.root_add(k, v)

    finished = False

    try:
            finished = shell.invoke(line)
    except APIError:
        traceback.print_exc()
        cmdstream.do_final_close()
        return 1
    except IOTileException as exc:
        print(exc.format())
        #if the command passed on the command line fails, then we should
        #just exit rather than drop the user into a shell.
        cmdstream.do_final_close()
        return 1
    except Exception:
        #Catch all exceptions because otherwise we won't properly close cmdstreams
        #since the program will be said to except 'abnormally'
        traceback.print_exc()
        cmdstream.do_final_close()
        return 1

    if finished:
        cmdstream.do_final_close()
        return 0

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

    #We ended the initial command with a context, start a shell
    try:
        while True:
            linebuf = raw_input("(%s) " % shell.context_name())

            # Skip comments automatically
            if len(linebuf) > 0 and linebuf[0] == '#':
                continue

            line = shlex.split(linebuf, posix=shell.posix_lex)

            #Automatically remove enclosing double quotes on windows since they are not removed by shlex in nonposix mode
            def remove_quotes(x):
                if len(x) > 0 and x.startswith(("'", '"')) and x[0] == x[-1]:
                    return x[1:-1]

                return x

            if not shell.posix_lex:
                line = map(remove_quotes, line)

            #Catch exception outside the loop so we stop invoking submethods if a parent
            #fails because then the context and results would be unpredictable
            try:
                finished = shell.invoke(line)
            except APIError:
                traceback.print_exc()
            except IOTileException as exc:
                print(exc.format())

            if shell.finished():
                break

    #Make sure to catch ^C and ^D so that we can cleanly dispose of subprocess resources if
    #there are any.
    except EOFError:
        print("")
    except KeyboardInterrupt:
        print("")
    finally:
        #Make sure we close any open CMDStream communication channels so that we don't lockup at exit
        cmdstream.do_final_close()
