"""A device model that constrains what a sensor graph can do.

Any device specific settings like how many inputs or outputs a
sensor graph can have or what sorts of streams are supported should
be specified in the device model and then is used during sensor graph
construction and processing to make sure the graph could be supported
by the desired device type.
"""

from builtins import str
from iotile.core.exceptions import ArgumentError


class DeviceModel(object):
    """A model of a device's sensor graph processor used to constrain behavior."""

    def __init__(self):
        self._properties = {}

        self._add_property(u'max_node_inputs', 2)
        self._add_property(u'max_node_outputs', 4)
        self._add_property(u'max_root_nodes', 8)
        self._add_property(u'max_streamers', 8)
        self._add_property(u'max_nodes', 32)
        self._add_property(u'max_storage_buffer', 16128)
        self._add_property(u'max_streaming_buffer', 48896)
        self._add_property(u'buffer_erase_size', 256)

    def _add_property(self, name, default_value):
        """Add a device property with a given default value.

        Args:
            name (str): The name of the property to add
            default_value (int, bool): The value of the property
        """

        name = str(name)
        self._properties[name] = default_value

    def set(self, name, value):
        """Set a device model property.

        Args:
            name (str): The name of the property to set
            value (int, bool): The value of the property to set
        """

        name = str(name)
        if name not in self._properties:
            raise ArgumentError("Unknown property in DeviceModel", name=name)

        self._properties[name] = value

    def get(self, name):
        """Get a device model property.

        Args:
            name (str): The name of the property to get
        """

        name = str(name)
        if name not in self._properties:
            raise ArgumentError("Unknown property in DeviceModel", name=name)

        return self._properties[name]
