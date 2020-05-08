from typing import List
import logging
import time
from statistics import mean

class reader_stats:

    def __init__(self, name: str, bin_count: int = 60, report_frequency: int = 10):
        self.logger = logging.getLogger(__name__)
        self.name = name
        self.bin_count = bin_count
        self.packets_seen_bins: List[int] = [0] * bin_count
        self.packets_forwarded_bins: List[int] = [0] * bin_count
        self.report_frequency = report_frequency
        self.next_report_time = time.monotonic() + report_frequency
        self.last_bin = 0

    def add_count(self, new_seen: int, new_forwarded: int):
        current_bin = int(time.monotonic()) % self.bin_count
        #self.logger.error("curent: %d", current_bin)
        if self.last_bin != current_bin:
            self.packets_seen_bins[current_bin] = new_seen
            self.packets_forwarded_bins[current_bin] = new_forwarded
        else:
            self.packets_seen_bins[current_bin] += new_seen
            self.packets_forwarded_bins[current_bin] += new_forwarded

        self.last_bin = current_bin

    def report(self, immediately: bool = False):
        if not immediately and time.monotonic() < self.next_report_time:
            return
        self.next_report_time += self.report_frequency
        #self.logger.error("reporting")

        last_bin = (int(time.monotonic()) - 1) % self.bin_count
        #self.logger.error("%d, %s", last_bin, str(self.packets_seen_bins))
        self.logger.error("%s Seen: %d, Avg: %d, Fwded: %d, Avg: %d", self.name,
               self.packets_seen_bins[last_bin], mean(self.packets_seen_bins),
               self.packets_forwarded_bins[last_bin], mean(self.packets_forwarded_bins))
