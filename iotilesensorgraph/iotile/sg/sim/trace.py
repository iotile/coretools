"""A list of trace actions that list what occured during a simulation.

SimulationTrace objects allow one to compare and save the important
details of a simulation while not saving all internal results that
are not directly visible to the external world and could change as
a result of different levels of optimization.
"""

from __future__ import (unicode_literals, absolute_import, print_function)
import json
from iotile.core.hw.reports import IOTileReading
from typedargs.exceptions import ArgumentError
from ..stream import DataStreamSelector, DataStream


class SimulationTrace(list):
    """A trace of all operations that occurred during an SG simulation.

    Traces are creating by attaching watchers to specific stream selectors
    and logging all activity in those streams.

    Args:
        readings (list of IOTileReading): The individual readings that are
            part of this trace.
        selectors (list of DataStreamSelector): The selectors that were used
            to produce this trace.  This information is saved along with the
            raw trace values so that we can compare apples to apples when
            comparing different traces.
    """

    def __init__(self, readings=None, selectors=None):
        if readings is None:
            readings = []
        if selectors is None:
            selectors = []

        self.selectors = selectors
        super(SimulationTrace, self).__init__(readings)

    def save(self, out_path):
        """Save an ascii representation of this simulation trace.

        Args:
            out_path (str): The output path to save this simulation trace.
        """

        out = {
            'selectors': [str(x) for x in self.selectors],
            'trace': [{'stream': str(DataStream.FromEncoded(x.stream)), 'time': x.raw_time, 'value': x.value, 'reading_id': x.reading_id} for x in self]
        }

        with open(out_path, "wb") as outfile:
            json.dump(out, outfile, indent=4)

    @classmethod
    def FromFile(cls, in_path):
        """Load a previously saved ascii representation of this simulation trace.

        Args:
            in_path (str): The path of the input file that we should load.

        Returns:
            SimulationTrace: The loaded trace object.
        """

        with open(in_path, "rb") as infile:
            in_data = json.load(infile)

        if not ('trace', 'selectors') in in_data:
            raise ArgumentError("Invalid trace file format", keys=in_data.keys(), expected=('trace', 'selectors'))

        selectors = [DataStreamSelector.FromString(x) for x in in_data['selectors']]
        readings = [IOTileReading(x['time'], DataStream.FromString(x['stream']).encode(), x['value'], reading_id=x['reading_id']) for x in in_data['trace']]

        return SimulationTrace(readings, selectors=selectors)
