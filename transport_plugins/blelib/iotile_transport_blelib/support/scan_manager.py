"""Helper class for sending advertisements to scan requesters."""

from typedargs.exceptions import ArgumentError
from ..interface.scan_delegate import BLEScanDelegate
from ..interface.advertisement import BLEAdvertisement

class _ScanRequester:
    def __init__(self, delegate: BLEScanDelegate, active: bool):
        self.delegate = delegate
        self.active = active


class BLEScanManager:
    """A helper class for maintaining state about scan requests.

    This class implements a pub/sub type pattern for determining:
    - if scanning is currently being requested by anyone.
    - if active-scanning is being requested by anyone.
    - what callbacks should be invoked when new advertisements are received.

    It manages users requesting access to BLE scan data by using a
    ``BLEScanDelegate`` protocol where each time scanning is enabled or
    disabled, a callback is made to indicate that on each requester. A
    separate callback is invoked for each bluetooth advertisement received.
    """

    def __init__(self):
        self.scanners = {}
        self._active_count = 0
        self._scanning = False
        self._active_scanning = False

    def request(self, tag: str, delegate: BLEScanDelegate, active=False):
        """Update the internal state with another scan requester."""

        if tag in self.scanners:
            raise ArgumentError("Attempted to add a scan requester twice: tag=%s" % tag)

        if delegate is None:
            delegate = BLEScanDelegate()

        self.scanners[tag] = _ScanRequester(delegate, active)

        if active:
            self._active_count += 1

        if self._scanning:
            delegate.scan_started()

    def release(self, tag: str, force: bool = False):
        """Remove a currently registered scan requester."""

        if tag not in self.scanners and not force:
            raise ArgumentError("Attempted to remove a scan requester that wasn't present: tag=%s"
                                % tag)

        if tag in self.scanners and self._scanning:
            info = self.scanners[tag]
            del self.scanners[tag]

            info.delegate.scan_stopped()
            if info.active:
                self._active_count -= 1

    def release_all(self):
        """Release all scanners."""

        to_release = list(self.scanners)
        for tag in to_release:
            self.release(tag)

    def is_scanning(self) -> bool:
        """Check if we are currently scanning."""

        return self._scanning

    def should_start(self) -> bool:
        """Check if we should start scanning."""

        return len(self.scanners) > 0 and not self._scanning

    def active_scan(self):
        """Check if we should scan in active scan mode."""

        return self._active_count > 0

    def should_restart(self) -> bool:
        """Check if we should reconfigure and restart scanning.

        This also checks if we should start scanning.
        """

        if self.should_start():
            return True

        if not self._scanning:
            return False

        if self._active_count == 0 and self._active_scanning:
            return True

        if self._active_count > 0 and not self._active_scanning:
            return True

        return False

    def should_stop(self) -> bool:
        """Check if we should stop scanning."""

        return len(self.scanners) == 0 and self._scanning

    def scan_started(self, active):
        """Notify that scanning has started or resumed."""

        if self._scanning:
            return

        self._scanning = True
        self._active_scanning = active

        for info in self.scanners.values():
            info.delegate.scan_started()

    def scan_stopped(self):
        """Notify that scanning has stopped or paused."""

        if not self._scanning:
            return

        self._scanning = False
        for info in self.scanners.values():
            info.delegate.scan_stopped()

    def handle_advertisement(self, advert: BLEAdvertisement):
        """Process a received ble advertisement."""

        if not self._scanning:
            return

        for info in self.scanners.values():
            info.delegate.on_advertisement(advert)
