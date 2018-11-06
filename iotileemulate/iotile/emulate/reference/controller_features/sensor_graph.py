"""Mixin for device updating via signed scripts.

Current State of Necessary TODOS:
- [ ] Support background task to actually handle graph tasks
- [ ] Add secondary background worker for sending rpcs
- [ ] Support persisting graph
- [ ] Support dumping and restoring state
- [ ] Support fill-stop mode
- [ ] Support direct interaction with the rsl
"""

from future.utils import viewitems
from iotile.core.hw.virtual import tile_rpc
from iotile.core.hw.reports import IOTileReading
from iotile.sg import SensorGraph, SensorLog
from ...virtual import SerializableState
from ..constants import rpcs


class SensorGraphSubsystem(object):
    """Container for sensorgraph state and workqueue."""

    def __init__(self, model):
        self.storage = SensorLog(model=model)
        self.graph = SensorGraph(self.storage, model=model)
        self.persisted_data = {'nodes': [], 'streamers': []}
        self.dump_walker = None

    def clear_and_load_persisted(self):
        """Clear the sensorgraph and load in the persisted one."""

        raise NotImplementedError()


class SensorGraphMixin(object):
    """Reference controller subsystem for sensor_graph.

    This class must be used as a mixin with a ReferenceController base class.

    Args:
        model (DeviceModel): The sensorgraph device model to use to calculate
            constraints and other operating parameters.
    """


    def __init__(self, model):
        self.sensor_graph = SensorGraphSubsystem(model)

    def _handle_reset(self):
        pass  #FIXME: Load in the persisted sensorgraph and clear everything

