"""iotile-supervisor script main entry point."""

import sys
import logging
import json
import argparse
from iotile.core.utilities import SharedLoop
from .gateway import IOTileGateway

class ScriptError(Exception):
    """An error raised to end the command line script with an error code."""

    def __init__(self, message, code):
        super(ScriptError, self).__init__(message)

        self.msg = message
        self.code = code


def build_parser():
    """Build the script's argument parser."""

    parser = argparse.ArgumentParser(description="The IOTile task supervisor")
    parser.add_argument('-c', '--config', help="config json with options")
    parser.add_argument('-v', '--verbose', action="count", default=0, help="Increase logging verbosity")

    return parser


def configure_logging(verbosity):
    """Set up the global logging level.

    Args:
        verbosity (int): The logging verbosity
    """

    root = logging.getLogger()

    formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(levelname).3s %(name)s %(message)s',
                                  '%y-%m-%d %H:%M:%S')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    loglevels = [logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]
    if verbosity >= len(loglevels):
        verbosity = len(loglevels) - 1

    level = loglevels[verbosity]

    root.setLevel(level)
    root.addHandler(handler)


def main(argv=None, loop=SharedLoop, max_time=None):
    """Main entry point for iotile-gateway."""
    should_raise = argv is not None

    if argv is None:
        argv = sys.argv[1:]

    parser = build_parser()
    cmd_args = parser.parse_args(argv)

    configure_logging(cmd_args.verbose)
    logger = logging.getLogger(__name__)

    try:
        args = {}
        if cmd_args.config is not None:
            try:
                with open(cmd_args.config, "r") as conf:
                    args = json.load(conf)
            except IOError as exc:
                raise ScriptError("Could not open config file %s due to %s"
                                  % (cmd_args.config, str(exc)), 2)
            except ValueError as exc:
                raise ScriptError("Could not parse JSON from config file %s due to %s"
                                  % (cmd_args.config, str(exc)), 3)
            except TypeError as exc:
                raise ScriptError("You must pass the path to a json config file", 4)

        logger.critical("Starting gateway")

        gateway = IOTileGateway(args, loop=loop)
        loop.run_coroutine(gateway.start())

        logger.critical("Gateway running")

        # Run forever until we receive a ctrl-c
        # (allow quitting early after max_time seconds for testing)
        loop.wait_for_interrupt(max_time=max_time)

        loop.run_coroutine(gateway.stop())
    except ScriptError as exc:
        if should_raise:
            raise exc

        logger.fatal("Quitting due to error: %s", exc.msg)
        return exc.code
    except Exception as exc:  # pylint: disable=W0703
        if should_raise:
            raise exc

        logger.exception("Fatal error running gateway")
        return 1

    return 0
