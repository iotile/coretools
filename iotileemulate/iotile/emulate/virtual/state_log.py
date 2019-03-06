"""A list of changes to an emulated device for verification purposes."""

import sys
import threading
from collections import namedtuple
import csv
from time import monotonic

StateChange = namedtuple("StateChange", ['time', 'tile', 'property', 'value', 'string_value'])


class EmulationStateLog(object):
    """A thread safe list of state changes to an emulated device."""

    def __init__(self):
        self.changes = []
        self.tracking = False
        self._lock = threading.Lock()
        self._whitelist = set()

    def track_change(self, tile, property_name, value, formatter=None):
        """Record that a change happened on a given tile's property.

        This will as a StateChange object to our list of changes if we
        are recording changes, otherwise, it will drop the change.

        Args:
            tile (int): The address of the tile that the change happened on.
            property_name (str): The name of the property that changed.
            value (object): The new value assigned to the property.
            formatter (callable): Optional function to convert value to a
                string.  This function will only be called if track_changes()
                is enabled and `name` is on the whitelist for properties that
                should be tracked.  If `formatter` is not passed or is None,
                it will default to `str`.
        """

        if not self.tracking:
            return

        if len(self._whitelist) > 0 and (tile, property_name) not in self._whitelist:
            return

        if formatter is None:
            formatter = str

        change = StateChange(monotonic(), tile, property_name, value, formatter(value))

        with self._lock:
            self.changes.append(change)

    def enable(self):
        """Start tracking changes."""

        self.tracking = True

    def set_whitelist(self, whitelist):
        """Only record changes to the given list of (tile, name) properties.

        Adding a whitelist allows you to ignore changes that you don't care
        about.  The argument should be a list of tuples with 2 members:
        (tile_adress, property_name)

        Once specified, only property changes in the whitelist will be recorded.

        You can clear a whitelist by calling `set_whitelist([])`

        Args:
            whitelist (list of (tile, property_name)): A list of all properties that
                should be included in the emulation state log.
        """

        self._whitelist = set(whitelist)

    def disable(self):
        """Stop tracking changes."""

        self.tracking = False

    def dump(self, out_path, header=True):
        """Save this list of changes as a csv file at out_path.

        The format of the output file will be a CSV with 4 columns:
        timestamp, tile address, property, string_value

        There will be a single header row starting the CSV output unless
        header=False is passed.

        Args:
            out_path (str): The path where we should save our current list of
                changes.
            header (bool): Whether we should include a header row in the csv
                file.  Defaults to True.
        """

        # See https://stackoverflow.com/a/3348664/9739119 for why this is necessary
        if sys.version_info[0] < 3:
            mode = "wb"
        else:
            mode = "w"

        with open(out_path, mode) as outfile:
            writer = csv.writer(outfile, quoting=csv.QUOTE_MINIMAL)
            if header:
                writer.writerow(["Timestamp", "Tile Address", "Property Name", "Value"])

            for entry in self.changes:
                writer.writerow([entry.time, entry.tile, entry.property, entry.string_value])
