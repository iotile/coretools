import sys
import logging
import argparse
import time
import queue


from iotile.core.utilities.linebuffer_ui import LinebufferUI
from iotile.core.utilities.async_tools import SharedLoop

from iotile_transport_bled112.hardware.async_central import BLED112Central
from iotile_transport_blelib.interface import BLEScanDelegate

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

    parser.add_argument('port', nargs='?', default=None, help="(optional) bled112 device to use")
    parser.add_argument('-c', '--connect', default=None, help="Device MAC address to connect to before scanning")
    parser.add_argument('-a', '--active', action="store_true", help="use active scanning")
    parser.add_argument('-s', '--statistics', action="store_true", help="Print statistics")
    parser.add_argument('-i', '--interval', type=float, help="Interval to print incremental statistics")
    parser.add_argument('-d', '--display', choices=['dash', 'log', 'none'], default='none',
                        help="The type of display to show")

    return parser.parse_args(argv)


def run_dashboard(updates):
    shared = [0]
    last_update = time.monotonic()
    rate = None
    peak_rate = None
    min_rate = None

    last_count = 0

    def _poll():
        results = []
        try:
            while True:
                results.append(updates.get_nowait())
                shared[0] += 1
        except queue.Empty:
            pass

        return results

    def _rate_string(rate):
        if rate is None:
            return "waiting"

        return "%.0f/s" % rate

    def _rate_strings(rate, trough, peak):
        return _rate_string(rate), _rate_string(trough), _rate_string(peak)

    def _title(_items):
        nonlocal last_count, last_update, rate, min_rate, peak_rate

        now = time.monotonic()

        if (now - last_update) > 5:
            new_count = shared[0]
            delta = new_count - last_count

            rate = delta / (now - last_update)
            if peak_rate is None or rate > peak_rate:
                peak_rate = rate
            if min_rate is None or rate < min_rate:
                min_rate = rate

            last_count = new_count
            last_update = now

        return ['Advertisement Dashboard',
                '  Packet Statistics (5s window): last=%s  min=%s  max=%s          '
                % _rate_strings(rate, min_rate, peak_rate)]

    def _text(item):
        return "%s: (rssi = %.0f)" % (item.sender, item.rssi)

    def _sort_order(item):
        return item.sender

    def _hash(item):
        return item.sender

    line_ui = LinebufferUI(_poll, _hash, _text, sortkey_func=_sort_order, title=_title)
    line_ui.run()


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

        if args.connect:
            SharedLoop.run_coroutine(central._bled112.connect(args.connect))
            logger.info("Connected to %s, beginning scan", args.connect)

        try:
            updates = queue.Queue()
            log_print = args.display == 'log'
            delegate = ScanDelegate(log_print, updates)
            SharedLoop.run_coroutine(central.request_scan('observer', args.active, delegate))

            if args.display == 'dash':
                run_dashboard(updates)
            else:
                while True:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            SharedLoop.run_coroutine(central.stop())
    except:
        logger.exception("Error running script.")

if __name__ == '__main__':
    sys.exit(main())
