# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

import sys
import os
import threading
import traceback
import argparse
import logging

from typedargs.shell import HierarchicalShell
from typedargs import type_system
from iotile.core.exceptions import IOTileException
from iotile.core.dev.registry import ComponentRegistry
from iotile.core.utilities import SharedLoop

DESCRIPTION = \
    """Create an interactive shell that explores the IOTile API.

    This tool allows you to run commands that are defined in either CoreTools, or
    in a registered plugin.  You can do things like build IOTile firmware or
    control an IOTile device.

    If you wish enable logging to debug something that is not working correctly,
    you can do so by passing a combination of -v, -l, -e and -i flags as needed.
    See iotile --help for more details.

    **NB, if you want to pass global arguments to enable logging you must do so
    before the first command you pass otherwise the global arguments will be
    interpreted as arguments to your commands.**
    """


def timeout_thread_handler(timeout, stop_event):
    """A background thread to kill the process if it takes too long.

    Args:
        timeout (float): The number of seconds to wait before killing
            the process.
        stop_event (Event): An optional event to cleanly stop the background
            thread if required during testing.
    """

    stop_happened = stop_event.wait(timeout)
    if stop_happened is False:
        print("Killing program due to %f second timeout" % timeout)

    os._exit(2)


def create_parser():
    """Create the argument parser for iotile."""
    parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-v', '--verbose', action="count", default=0, help="Increase logging level (goes error, warn, info, debug)")
    parser.add_argument('-l', '--logfile', help="The file where we should log all logging messages")
    parser.add_argument('-i', '--include', action="append", default=[], help="Only include the specified loggers")
    parser.add_argument('-e', '--exclude', action="append", default=[], help="Exclude the specified loggers, including all others")
    parser.add_argument('-q', '--quit', action="store_true", help="Do not spawn a shell after executing any commands")
    parser.add_argument('-t', '--timeout', type=float, help="Do not allow this process to run for more than a specified number of seconds.")
    parser.add_argument('commands', nargs=argparse.REMAINDER, help="The command(s) to execute")

    return parser


def parse_global_args(argv):
    """Parse all global iotile tool arguments.

    Any flag based argument at the start of the command line is considered as
    a global flag and parsed.  The first non flag argument starts the commands
    that are passed to the underlying hierarchical shell.

    Args:
        argv (list): The command line for this command

    Returns:
        Namespace: The parsed arguments, with all of the commands that should
            be executed in an iotile shell as the attribute 'commands'
    """

    parser = create_parser()
    args = parser.parse_args(argv)

    should_log = args.include or args.exclude or (args.verbose > 0)
    verbosity = args.verbose

    root = logging.getLogger()

    if should_log:
        formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(levelname).3s %(name)s %(message)s',
                                      '%y-%m-%d %H:%M:%S')
        if args.logfile:
            handler = logging.FileHandler(args.logfile)
        else:
            handler = logging.StreamHandler()

        handler.setFormatter(formatter)

        if args.include and args.exclude:
            print("You cannot combine whitelisted (-i) and blacklisted (-e) loggers, you must use one or the other.")
            sys.exit(1)

        loglevels = [logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]
        if verbosity >= len(loglevels):
            verbosity = len(loglevels) - 1

        level = loglevels[verbosity]

        if args.include:
            for name in args.include:
                logger = logging.getLogger(name)
                logger.setLevel(level)
                logger.addHandler(handler)

            root.addHandler(logging.NullHandler())
        else:
            # Disable propagation of log events from disabled loggers
            for name in args.exclude:
                logger = logging.getLogger(name)
                logger.disabled = True

            root.setLevel(level)
            root.addHandler(handler)
    else:
        root.addHandler(logging.NullHandler())

    return args


def setup_completion(shell):
    """Setup readline to tab complete in a cross platform way."""

    # Handle special case of importing pyreadline on Windows
    # See: http://stackoverflow.com/questions/6024952/readline-functionality-on-windows-with-python-2-7
    import glob
    try:
        import readline
    except ImportError:
        import pyreadline as readline

    def _complete(text, state):
        buf = readline.get_line_buffer()
        if buf.startswith('help ') or " " not in buf:
            return [x for x in shell.valid_identifiers() if x.startswith(text)][state]

        return (glob.glob(os.path.expanduser(text)+'*')+[None])[state]

    readline.set_completer_delims(' \t\n;')
    # Handle Mac OS X special libedit based readline
    # See: http://stackoverflow.com/questions/7116038/python-tab-completion-mac-osx-10-7-lion
    if readline.__doc__ is not None and 'libedit' in readline.__doc__:
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")

    readline.set_completer(_complete)


def main(argv=None):
    """Run the iotile shell tool.

    You can optionally pass the arguments that should be run
    in the argv parameter.  If nothing is passed, the args
    are pulled from sys.argv.

    The return value of this function is the return value
    of the shell command.
    """

    if argv is None:
        argv = sys.argv[1:]

    args = parse_global_args(argv)

    type_system.interactive = True
    line = args.commands

    timeout_thread = None
    timeout_stop_event = threading.Event()

    if args.timeout:
        timeout_thread = threading.Thread(target=timeout_thread_handler, args=(args.timeout, timeout_stop_event))
        timeout_thread.daemon = True
        timeout_thread.start()

    shell = HierarchicalShell('iotile')

    shell.root_add("registry", "iotile.core.dev.annotated_registry,registry")
    shell.root_add("config", "iotile.core.dev.config,ConfigManager")
    shell.root_add('hw', "iotile.core.hw.hwmanager,HardwareManager")

    reg = ComponentRegistry()
    plugins = reg.list_plugins()
    for key, val in plugins.items():
        shell.root_add(key, val)

    finished = False

    try:
        if len(line) > 0:
            finished = shell.invoke(line)
    except IOTileException as exc:
        print(exc.format())
        # if the command passed on the command line fails, then we should
        # just exit rather than drop the user into a shell.
        SharedLoop.stop()
        return 1
    except Exception:  # pylint:disable=broad-except; We need to make sure we always call cmdstream.do_final_close()
        # Catch all exceptions because otherwise we won't properly close cmdstreams
        # since the program will be said to except 'abnormally'
        traceback.print_exc()
        SharedLoop.stop()
        return 1

    # If the user tells us to never spawn a shell, make sure we don't
    # Also, if we finished our command and there is no context, quit now
    if args.quit or finished:
        SharedLoop.stop()
        return 0

    setup_completion(shell)

    # We ended the initial command with a context, start a shell
    try:
        while True:
            try:
                linebuf = input("(%s) " % shell.context_name())

                # Skip comments automatically
                if len(linebuf) > 0 and linebuf[0] == '#':
                    continue
            except KeyboardInterrupt:
                print("")
                continue

            # Catch exception outside the loop so we stop invoking submethods if a parent
            # fails because then the context and results would be unpredictable
            try:
                finished = shell.invoke_string(linebuf)
            except KeyboardInterrupt:
                print("")
                if timeout_stop_event.is_set():
                    break
            except IOTileException as exc:
                print(exc.format())
            except Exception:  #pylint:disable=broad-except;
                # We want to make sure the iotile tool never crashes when in interactive shell mode
                traceback.print_exc()

            if shell.finished():
                break

    # Make sure to catch ^C and ^D so that we can cleanly dispose of subprocess resources if
    # there are any.
    except EOFError:
        print("")
    except KeyboardInterrupt:
        print("")
    finally:
        # Make sure we close any open CMDStream communication channels so that we don't lockup at exit
        SharedLoop.stop()

    # Make sure we cleanly join our timeout thread before exiting
    if timeout_thread is not None:
        timeout_stop_event.set()
        timeout_thread.join()


if __name__ == '__main__':
    sys.exit(main())
