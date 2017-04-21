import signal
import logging
import sys
import tornado.ioloop
import json
from tornado.options import define, parse_command_line, options

from iotile.core.exceptions import ArgumentError
from ws_handler import ServiceWebSocketHandler
from service_manager import ServiceManager

should_close = False

define('config', help="Optional config file for defining expected services and our port for connections")


def quit_signal_handler(signum, frame):
    """Signal handler to catch ^C and cleanly shut down."""

    global should_close

    should_close = True
    log = logging.getLogger('tornado.general')
    log.critical('Received stop signal, attempting to stop')


def try_quit():
    """Periodic callback to attempt to cleanly shut down this gateway."""
    global should_close

    if not should_close:
        return

    log = logging.getLogger('tornado.general')

    log.critical("Stopping Supervisor Service")

    tornado.ioloop.IOLoop.instance().stop()
    log.critical('Stopping event loop and shutting down')


def main():
    """Main entry point for iotile-supervisor."""
    global should_close

    log = logging.getLogger('tornado.general')

    parse_command_line()

    config_file = options.config
    args = {}

    if config_file is not None:
        try:
            with open(config_file, "rb") as conf:
                args = json.load(conf)
        except IOError, exc:
            raise ArgumentError("Could not open required config file", path=config_file, error=str(exc))
        except ValueError, exc:
            raise ArgumentError("Could not parse JSON from config file", path=config_file, error=str(exc))
        except TypeError, exc:
            raise ArgumentError("You must pass the path to a json config file", path=config_file)

    if 'port' not in args:
        args['port'] = 9400

    if 'expected_services' not in args:
        args['expected_services'] = {}

    service_manager = ServiceManager(args['expected_services'])

    loop = tornado.ioloop.IOLoop.instance()

    signal.signal(signal.SIGINT, quit_signal_handler)

    # Make sure we have a way to cleanly break out of the event loop on Ctrl-C
    tornado.ioloop.PeriodicCallback(try_quit, 100).start()

    port = args.get('port')

    app = tornado.web.Application([
        (r'/services', ServiceWebSocketHandler, {'manager': service_manager, 'logger': log}),
    ])

    log.info("Starting IOTile supervisor service over websockets on port %d" % port)
    app.listen(port)

    loop.start()

    # The loop has been closed, finish and quit
    log.critical("Done stopping loop")
