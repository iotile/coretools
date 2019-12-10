import sys
import logging
import argparse
import time
import queue


from iotile.core.utilities.linebuffer_ui import LinebufferUI
from iotile.core.utilities.async_tools import SharedLoop

from iotile_transport_bled112.hardware.async_central import BLED112Central
from iotile_transport_bled112.hardware.ble import BLEScanDelegate, errors

class ScanDelegate(BLEScanDelegate):
    def __init__(self, print_=False, updates=None):
        self.print_ = print_
        self.updates = updates
        self._logger = logging.getLogger(__name__)

    def scan_started(self):
        self._logger.info("Scan started")

    def scan_stopped(self):
        self._logger.info("Scan stopped")

    def on_advertisement(self, advert):
        """Process a received ble advertisement."""

        if self.print_:
            print("%s: (rssi = %.0f)" % (advert.sender, advert.rssi))

        if self.updates is not None:
            self.updates.put(advert)


def configure_logging(verbose):
    """Configure logging verbosity according to -q and -v flags.

    Default behavior with no flags passed is to log critical messages only.
    Passing -q turns off all logging.  Passing one more -v flags increases
    the logging verbosity level.
    """

    if verbose is None:
        verbose = 0

    root = logging.getLogger()

    if verbose >= 0:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(levelname).3s %(name)s %(message)s',
                                      '%y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        loglevels = [logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]

        if verbose >= len(loglevels):
            verbose = len(loglevels) - 1

        level = loglevels[verbose]
        root.setLevel(level)
        root.addHandler(handler)
    else:
        root.addHandler(logging.NullHandler())


def parse_args(argv):
    """Parse command line arguments."""

    parser = argparse.ArgumentParser(description="A simple BLE observer using the bled112 dongle")

    parser.add_argument('-q', '--quiet', dest="verbose", action="store_const", const=-1, help="Turn off all logging output")
    parser.add_argument('-v', '--verbose', action="count", default=0, help="Increase logging level (goes error, warn, info, debug)")

    parser.add_argument('-p', '--port', default=None, help="(optional) bled112 device to use")
    parser.add_argument('device', help="Device MAC address to connect to")

    return parser.parse_args(argv)


def main(argv=None):
    """Script main entry point."""

    logger = logging.getLogger(__name__)
    try:
        if argv is None:
            argv = sys.argv[1:]

        args = parse_args(argv)

        configure_logging(args.verbose)

        central = BLED112Central(args.port)

        SharedLoop.run_coroutine(central.start())

        broken = False
        try:
            while True:
                try:
                    peripheral = SharedLoop.run_coroutine(central.connect(args.device))
                    SharedLoop.run_coroutine(central._bled112.start_scan(active=False))
                    SharedLoop.run_coroutine(central.disconnect(peripheral))
                except KeyboardInterrupt:
                    raise
                except errors.FatalAdapterError:
                    logger.exception("Fatal adapter error, stopping")
                    broken = True
                    break
                except:
                    logger.exception("Error running connection loop")
        except KeyboardInterrupt:
            pass
        finally:
            if not broken:
                SharedLoop.run_coroutine(central.stop())
    except:
        logger.exception("Error running script.")

if __name__ == '__main__':
    sys.exit(main())
