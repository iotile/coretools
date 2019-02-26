"""iotile-gateway script main entry point."""

import signal
import logging
import json
from iotilegateway.gateway import IOTileGateway
from tornado.options import define, parse_command_line, options
from iotile.core.exceptions import ArgumentError

import threading
import asyncio
from iotile.core.utilities.event_loop import EventLoop

define('config', help="Config file for defining what adapters and agents to use")


def main():
    """Main entry point for iotile-gateway."""

    gateway = None
    logging.basicConfig(format='%(levelname)-.1s-%(asctime)-15s-%(module)-10s:%(lineno)-4s %(message)s')
    log = logging.getLogger(__name__)

    def quit_signal_handler(signum, frame):  # pylint: disable=W0613
        """Signal handler to catch ^C and cleanly shut down."""

        log.critical("In quit signal handler.")

        if gateway is not None:
            log.critical("Calling stop on gateway loop")
            gateway.stop_from_signal()

    #forever = threading.Event()

    try:
        parse_command_line()

        config_file = options.config
        if config_file is None:
            log.critical("You must pass a config file using --config=<path to file>")
            return 1

        try:
            with open(config_file, "r") as conf:
                args = json.load(conf)
        except IOError as exc:
            raise ArgumentError("Could not open required config file", path=config_file, error=str(exc))
        except ValueError as exc:
            raise ArgumentError("Could not parse JSON from config file", path=config_file, error=str(exc))
        except TypeError:
            raise ArgumentError("You must pass the path to a json config file", path=config_file)

        #signal.signal(signal.SIGINT, quit_signal_handler)

        el = EventLoop()

        el.start()

        gateway = IOTileGateway(args)

        el.add_task(gateway.run())

    except Exception:  # pylint: disable=W0703
        log.exception("Fatal error starting gateway")

    print("after gateway main")

    import time

    try:
        #forever.wait()
        while (1):
            for thread in threading.enumerate():
                print(thread)
            time.sleep(1)
    except KeyboardInterrupt:
        print("it's been forever")
        el.stop_loop_clean()


if __name__ == '__main__':
    main()
