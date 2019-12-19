"""Base interface defining an object that receives callbacks when new devices are seen."""

from typing import Protocol
from .advertisement import BLEAdvertisement

class BLEScanDelegate(Protocol):
    """Generic protocol for anyone wanting access to ble advertisements.

    Users who want a callback for each ble advertisement should implement this
    class.  They will observe the following behavior:

    1. Their scan_started callback will be called whenever the underlying hardware
       begins or resumes scanning.  It will be called at least once before any
       calls to ``on_advertisement`` are made.
    2. ``scan_stopped`` will be called exactly once for each call to ``scan_started``
       and ``scan_started`` will only be called once before a call to ``scan_stopped``.
    3. ``on_advertisement`` will be called exactly once for each advertisement seen
       by the bluetooth hardware.
    """

    def scan_started(self):
        """Callback when the bluetooth hardware begins scanning."""

    def scan_stopped(self):
        """Callback when the bluetooth hardware stops scanning."""

    def on_advertisement(self, advert: BLEAdvertisement):
        """Callback for each advertisement seen by the bluetooth hardware.

        If active-scanning is enabled and a device provided by advertisement
        and scan response data, then ``advert`` will have both packets.
        Otherwise, there will be no scan response data included.

        Args:
            advert: The parsed ble advertisement that was received.
        """


class EmptyScanDelegate:
    """An empty scan delegate that discards all information."""

    def scan_started(self):
        """Callback when the bluetooth hardware begins scanning."""

    def scan_stopped(self):
        """Callback when the bluetooth hardware stops scanning."""

    def on_advertisement(self, advert: BLEAdvertisement):
        """Callback for each advertisement seen by the bluetooth hardware."""
