"""Standard implementation of AbstractDeviceAdapter."""

import logging
from iotile.core.exceptions import ArgumentError
from iotile.core.utilities import SharedLoop

from .abstract import AbstractDeviceAdapter
from .mixin_conndata import PerConnectionDataMixin
from .mixin_notifications import BasicNotificationMixin
from ...exceptions import DeviceAdapterError

_MISSING = object()


class StandardDeviceAdapter(PerConnectionDataMixin,
                            BasicNotificationMixin,
                            AbstractDeviceAdapter):
    """Standard basic implementation of AbstractDeviceAdapter.

    This class adds utility and convenience functions that are typically
    needed for building real DeviceAdapters as well as base implementations of
    all required :class:AbstractDeviceAdapter methods.  The base
    implementations don't do anything except raise an error saying the
    operation is not supported so subclasses can add features one at at a time
    until they support all of the chosen interfaces.

    Most real DeviceAdapters should inherit from this class rather than
    directly from AbstractDeviceAdapter unless you are doing some really
    special and know why it's better to avoid the helper methods inside this
    class.


    Key Features
    ------------

    1. A default implementation of ``get_config`` and ``set_config`` based on
       an internal dictionary.  This is typically all you need for a normal
       DeviceAdapter.

    2. A per-connection dictionary that you can use to store and fetch information
       that is needed on a per connection basis.  See :meth:`_get_property` and
       :meth:`_track_property`.  You can also use :meth:`_ensure_connection` as
       a simple way to fail a method if it requires a valid connection.  This check
       happens automatically inside :meth:`_get_property`.  This is provided by the
       mixin class :class:`PerConnectionDataMixin`.

    3. A default implementation of notification callbacks using a BackgroundEventLoop
       passed into the constructor.  This is provided by the mixin class
       :class:`BasicNotificationMixin`.

    If you want to include one or more of those mixins in a class that does
    not inherit from StandardDeviceAdapter, you are free to use them directly.


    Subclassing
    -----------

    The only two methods that you need to provide to subclass StandardDeviceAdapter are:

    - ``async def start()``: Start your device adapter
    - ``async def stop()``: Stop your device adapter

    All other required methods have safe default implementations.  When you
    want to send notifications on events, you should await
    :meth:`_notify_event`.


    More Information
    ----------------

    Most of the methods you need to implement and the contracts that they
    must satisfy is listed with :class:`abstract.AbstractDeviceAdapter`.

    - See :class:`abstract.AbstractDeviceAdapter`
    - See :mod:`iotile.core.hw.adapter.abstract`


    Args:
        loop (BackgroundEventLoop): The event loop that we should use to
            run our notification callbacks.
        name (str): Optional name for the logger
    """

    MAX_CONNECTIONS = 1
    """The default number of maximum simultaneous connections we support."""

    def __init__(self, name=__name__, loop=SharedLoop):
        PerConnectionDataMixin.__init__(self)
        BasicNotificationMixin.__init__(self, loop)
        AbstractDeviceAdapter.__init__(self)

        self._logger = logging.getLogger(name)
        self._next_conn_id = 0
        self._config = {}

    def get_config(self, name, default=_MISSING):
        """Get a configuration setting from this DeviceAdapter.

        See :meth:`AbstractDeviceAdapter.get_config`.
        """

        val = self._config.get(name, default)
        if val is _MISSING:
            raise ArgumentError("DeviceAdapter config {} did not exist and no default".format(name))

        return val

    def set_config(self, name, value):
        """Adjust a configuration setting on this DeviceAdapter.

        See :meth:`AbstractDeviceAdapter.set_config`.
        """

        self._config[name] = value

    def can_connect(self):
        """Return whether this device adapter can accept another connection.

        We check the config property 'max_connections' with the default of
        self.MAX_CONNECTIONS and return True if there are fewer active
        connections than that maximum number.

        See :meth:`AbstractDeviceAdapter.can_connect`.
        """

        return len(self._connections) < self.get_config('max_connections', self.MAX_CONNECTIONS)

    def unique_conn_id(self):
        """Return a new, unique connection id.

        See :meth:`AbstractDeviceAdapter.unique_conn_id`.
        """

        conn_id = self._next_conn_id
        self._next_conn_id += 1

        return conn_id

    async def start(self):
        """Start the device adapter.

        See :meth:`AbstractDeviceAdapter.start`.
        """

    async def stop(self):
        """Stop the device adapter.

        See :meth:`AbstractDeviceAdapter.stop`.
        """

    async def connect(self, conn_id, connection_string):
        """Connect to a device.

        See :meth:`AbstractDeviceAdapter.connect`.
        """

        raise DeviceAdapterError(conn_id, 'connect', 'not supported')

    async def disconnect(self, conn_id):
        """Disconnect from a connected device.

        See :meth:`AbstractDeviceAdapter.disconnect`.
        """

        raise DeviceAdapterError(conn_id, 'disconnect', 'not supported')

    async def open_interface(self, conn_id, interface):
        """Open an interface on an IOTile device.

        See :meth:`AbstractDeviceAdapter.open_interface`.
        """

        raise DeviceAdapterError(conn_id, 'open_interface {}'.format(interface),
                                 'not supported')

    async def close_interface(self, conn_id, interface):
        """Close an interface on this IOTile device.

        See :meth:`AbstractDeviceAdapter.close_interface`.
        """

        raise DeviceAdapterError(conn_id, 'close_interface {}'.format(interface),
                                 'not supported')

    async def probe(self):
        """Probe for devices connected to this adapter.

        See :meth:`AbstractDeviceAdapter.probe`.
        """

        raise DeviceAdapterError(None, 'probe', 'not supported')

    async def send_rpc(self, conn_id, address, rpc_id, payload, timeout):
        """Send an RPC to a device.

        See :meth:`AbstractDeviceAdapter.send_rpc`.
        """

        raise DeviceAdapterError(conn_id, 'send rpc', 'not supported')

    async def debug(self, conn_id, name, cmd_args):
        """Send a debug command to a device.

        See :meth:`AbstractDeviceAdapter.debug`.
        """

        raise DeviceAdapterError(conn_id, 'debug', 'not supported')

    async def send_script(self, conn_id, data):
        """Send a a script to a device.

        See :meth:`AbstractDeviceAdapter.send_script`.
        """

        raise DeviceAdapterError(conn_id, 'send_script', 'not supported')
