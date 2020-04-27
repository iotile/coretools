"""Base interface defining an object that receives callbacks when new devices are seen."""

from typing_extensions import Protocol
from .advertisement import BLEAdvertisement

class BLEScanDelegate(Protocol):
    def scan_started(self):
        pass

    def scan_stopped(self):
        pass

    def on_advertisement(self, advert: BLEAdvertisement):
        pass


class EmptyScanDelegate:
    def scan_started(self):
        pass

    def scan_stopped(self):
        pass

    def on_advertisement(self, advert: BLEAdvertisement):
        pass
