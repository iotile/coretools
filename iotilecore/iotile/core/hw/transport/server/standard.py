"""A reference implementation of AbstractDeviceServer designed to be subclassed.

:class:`StandardDeviceServer` is a full-featured implementation of the
:class:`AbstractDeviceServer` interface.  See the class docstring for
more information but all that is required to build a concrete device
server on top of StandardDeviceServer is to just handle receiving messages
from clients and calling the appropriate method.  Allocating and freeing
per-client resources is handled internally to make sure that nothing
leaks if clients unexpectedly disconnect.

In particular there is no need to manually keep track of client connections
or manage notifications on behalf of a client.  That is all done internally
inside of StandardDeviceServer.

"""
import logging
import uuid
import inspect
from iotile.core.utilities import SharedLoop
from iotile.core.exceptions import ArgumentError
from ...exceptions import DeviceServerError
from .abstract import AbstractDeviceServer


class StandardDeviceServer(AbstractDeviceServer):
    """A standard reference implementation of AbstractDeviceServer.

    This class is designed to provide the basic set of features that
    any normal AbstractDeviceServer needs.  In particular, it handles
    the three critical aspects of being a device server:

    - managing per-client data and cleaning up after a client is gone
    - managing per-connection data and cleaning up any lingering connections
      after a client is gone.
    - keeping track of which events should be forwarded to which clients.

    It does this by wrapping the underlying methods of the
    AbstractDeviceAdapter that it is given with versions that contain hooks to
    keep track of which client is connected to which device.

    These hooks automatically configure monitors on the underlying adapters
    and take care of removing those monitors when the client connection is
    destroyed for any reason.  Similarly any existing device connections are
    disconnected when a client goes away.

    This standard device server is completely functional on its own with
    no subclassing but developers will typically want to override the
    :meth:`start` and :meth:`stop` routines to actually start and stop their
    particular server (tcp, websockets, mqtt, etc).

    The interface that StandardDeviceServer presents is identical to
    AbstractDeviceAdapter but with the following modifications that make
    it suitable for use in a multi-client server:

    - All methods take a `client_id` parameter so that there is an explicit
      association of all operations with a single client.

    - All methods that previously took a `connection_id` now take a
      `connection_string`.  This is because we cannot guarantee that multiple
      clients would not choose the same connection_id and confuse the device
      adapter.  StandardDeviceServer handles assigning unique connection ids
      to all connections internally.  The connection ids are never exposed
      externally to the clients.  In case multiple device servers are attached
      to the same AbstractDeviceAdapter, they will generate connection ids by
      asking the abstract device adapter for a new unique connection id to
      ensure that they don't collide.

    .. important:

        If you override stop() make sure to call the super() implementation to
        ensure that client resources are properly released when the server
        stops.

    Args:
        adapter (AbstractDeviceAdapter): The underlying device adapter to use
            to find and connect to devices.
        args (dict): Any arguments that you wish to pass to the device server.
        loop (BackgroundEventLoop): The background loop that should be used
            to manage tasks.
    """

    def __init__(self, adapter, args=None, *, loop=SharedLoop):
        super(StandardDeviceServer, self).__init__(adapter, args, loop=loop)

        self.adapter = adapter
        self._clients = {}
        self._loop = loop
        self._logger = logging.getLogger(__name__)

    #pylint:disable=unused-argument;This method is designed to be overridden
    async def client_event_handler(self, client_id, event_tuple, user_data):
        """Method called to actually send an event to a client.

        Users of this class should override this method to actually forward
        device events to their clients.  It is called with the client_id
        passed to (or returned from) :meth:`setup_client` as well as the
        user_data object that was included there.

        The event tuple is a 3-tuple of:

        - connection string
        - event name
        - event object

        If you override this to be acoroutine, it will be awaited.  The
        default implementation just logs the event.

        Args:
            client_id (str): The client_id that this event should be forwarded
                to.
            event_tuple (tuple): The connection_string, event_name and event_object
                that should be forwarded.
            user_data (object): Any user data that was passed to setup_client.
        """

        conn_string, event_name, _event = event_tuple
        self._logger.debug("Ignoring event %s from device %s forwarded for client %s",
                           event_name, conn_string, client_id)

        return None

    def setup_client(self, client_id=None, user_data=None, scan=True, broadcast=False):
        """Setup a newly connected client.

        ``client_id`` must be unique among all connected clients.  If it is
        passed as None, a random client_id will be generated as a string and
        returned.

        This method reserves internal resources for tracking what devices this
        client has connected to and installs a monitor into the adapter on
        behalf of the client.

        It should be called whenever a new client connects to the device server
        before any other activities by that client are allowed.  By default,
        all clients start receiving ``device_seen`` events but if you want
        your client to also receive broadcast events, you can pass broadcast=True.

        Args:
            client_id (str): A unique identifier for this client that will be
                used to refer to it in all future interactions.  If this is
                None, then a random string will be generated for the client_id.
            user_data (object): An arbitrary object that you would like to store
                with this client and will be passed to your event handler when
                events are forwarded to this client.
            scan (bool): Whether to install a monitor to listen for device_found
                events.
            broadcast (bool): Whether to install a monitor to list for broadcast
                events.

        Returns:
            str: The client_id.

            If a client id was passed in, it will be the same as what was passed
            in.  If no client id was passed in then it will be a random unique
            string.
        """

        if client_id is None:
            client_id = str(uuid.uuid4())

        if client_id in self._clients:
            raise  ArgumentError("Duplicate client_id: {}".format(client_id))

        async def _client_callback(conn_string, _, event_name, event):
            event_tuple = (conn_string, event_name, event)
            await self._forward_client_event(client_id, event_tuple)

        client_monitor = self.adapter.register_monitor([], [], _client_callback)

        self._clients[client_id] = dict(user_data=user_data, connections={},
                                        monitor=client_monitor)

        self._adjust_global_events(client_id, scan, broadcast)
        return client_id

    async def start(self):
        """Start the server.

        See :meth:`AbstractDeviceServer.start`.
        """

    async def stop(self):
        """Stop the server and teardown any remaining clients.

        If your subclass overrides this method, make sure to call
        super().stop() to ensure that all devices with open connections from
        thie server are properly closed.

        See :meth:`AbstractDeviceServer.stop`.
        """

        clients = list(self._clients)

        for client in clients:
            self._logger.info("Tearing down client %s at server stop()", client)
            await self.teardown_client(client)

    async def teardown_client(self, client_id):
        """Release all resources held by a client.

        This method must be called and awaited whenever a client is
        disconnected.  It ensures that all of the client's resources are
        properly released and any devices they have connected to are
        disconnected cleanly.

        Args:
            client_id (str): The client that we should tear down.

        Raises:
            ArgumentError: The client_id is unknown.
        """

        client_info = self._client_info(client_id)

        self.adapter.remove_monitor(client_info['monitor'])
        conns = client_info['connections']

        for conn_string, conn_id in conns.items():
            try:
                self._logger.debug("Disconnecting client %s from conn %s at teardown", client_id, conn_string)
                await self.adapter.disconnect(conn_id)
            except:  #pylint:disable=bare-except; This is a finalization method that should not raise unexpectedly
                self._logger.exception("Error disconnecting device during teardown_client: conn_string=%s", conn_string)

        del self._clients[client_id]

    async def probe(self, client_id):
        """Probe for devices on behalf of a client.

        See :meth:`AbstractDeviceAdapter.probe`.

        Args:
            client_id (str): The client we are probing for.

        Raises:
            DeviceServerError: There is an issue with your client_id.
            DeviceAdapterError: The adapter had an issue probing.
        """

        self._client_info(client_id)

        await self.adapter.probe()

    async def connect(self, client_id, conn_string):
        """Connect to a device on behalf of a client.

        See :meth:`AbstractDeviceAdapter.connect`.

        Args:
            client_id (str): The client we are working for.
            conn_string (str): A connection string that will be
                passed to the underlying device adapter to connect.

        Raises:
            DeviceServerError: There is an issue with your client_id.
            DeviceAdapterError: The adapter had an issue connecting.
        """
        conn_id = self.adapter.unique_conn_id()

        self._client_info(client_id)

        await self.adapter.connect(conn_id, conn_string)
        self._hook_connect(conn_string, conn_id, client_id)

    async def disconnect(self, client_id, conn_string):
        """Disconnect from a device on behalf of a client.

        See :meth:`AbstractDeviceAdapter.disconnect`.

        Args:
            client_id (str): The client we are working for.
            conn_string (str): A connection string that will be
                passed to the underlying device adapter to connect.

        Raises:
            DeviceServerError: There is an issue with your client_id such
                as not being connected to the device.
            DeviceAdapterError: The adapter had an issue disconnecting.
        """

        conn_id = self._client_connection(client_id, conn_string)

        try:
            await self.adapter.disconnect(conn_id)
        finally:
            self._hook_disconnect(conn_string, client_id)

    async def open_interface(self, client_id, conn_string, interface):
        """Open a device interface on behalf of a client.

        See :meth:`AbstractDeviceAdapter.open_interface`.

        Args:
            client_id (str): The client we are working for.
            conn_string (str): A connection string that will be
                passed to the underlying device adapter.
            interface (str): The name of the interface to open.

        Raises:
            DeviceServerError: There is an issue with your client_id such
                as not being connected to the device.
            DeviceAdapterError: The adapter had an issue opening the interface.
        """

        conn_id = self._client_connection(client_id, conn_string)

        # Hook first so there is no race on getting the first event
        self._hook_open_interface(conn_string, interface, client_id)
        await self.adapter.open_interface(conn_id, interface)

    async def close_interface(self, client_id, conn_string, interface):
        """Close a device interface on behalf of a client.

        See :meth:`AbstractDeviceAdapter.close_interface`.

        Args:
            client_id (str): The client we are working for.
            conn_string (str): A connection string that will be
                passed to the underlying device adapter.
            interface (str): The name of the interface to close.

        Raises:
            DeviceServerError: There is an issue with your client_id such
                as not being connected to the device.
            DeviceAdapterError: The adapter had an issue closing the interface.
        """

        conn_id = self._client_connection(client_id, conn_string)

        await self.adapter.close_interface(conn_id, interface)
        self._hook_close_interface(conn_string, interface, client_id)

    #pylint:disable=too-many-arguments;This is a legacy method signature.
    async def send_rpc(self, client_id, conn_string, address, rpc_id, payload, timeout):
        """Send an RPC on behalf of a client.

        See :meth:`AbstractDeviceAdapter.send_rpc`.

        Args:
            client_id (str): The client we are working for.
            conn_string (str): A connection string that will be
                passed to the underlying device adapter to connect.
            address (int): The RPC address.
            rpc_id (int): The ID number of the RPC
            payload (bytes): The RPC argument payload
            timeout (float): The RPC's expected timeout to hand to the underlying
                device adapter.

        Returns:
            bytes: The RPC response.

        Raises:
            DeviceServerError: There is an issue with your client_id such
                as not being connected to the device.
            TileNotFoundError: The destination tile address does not exist
            RPCNotFoundError: The rpc_id does not exist on the given tile
            RPCErrorCode: The RPC was invoked successfully and wishes to fail
                with a non-zero status code.
            RPCInvalidIDError: The rpc_id is too large to fit in 16-bits.
            TileBusSerror: The tile was busy and could not respond to the RPC.
            Exception: The rpc raised an exception during processing.
            DeviceAdapterError: If there is a hardware or communication issue
                invoking the RPC.
        """

        conn_id = self._client_connection(client_id, conn_string)
        return await self.adapter.send_rpc(conn_id, address, rpc_id, payload, timeout)

    async def send_script(self, client_id, conn_string, script):
        """Send a script to a device on behalf of a client.

        See :meth:`AbstractDeviceAdapter.send_script`.

        Args:
            client_id (str): The client we are working for.
            conn_string (str): A connection string that will be
                passed to the underlying device adapter.
            script (bytes): The script that we wish to send.

        Raises:
            DeviceServerError: There is an issue with your client_id such
                as not being connected to the device.
            DeviceAdapterError: The adapter had a protocol issue sending the script.
        """

        conn_id = self._client_connection(client_id, conn_string)
        await self.adapter.send_script(conn_id, script)

    async def debug(self, client_id, conn_string, command, args):
        """Send a debug command to a device on behalf of a client.

        See :meth:`AbstractDeviceAdapter.send_script`.

        Args:
            client_id (str): The client we are working for.
            conn_string (str): A connection string that will be
                passed to the underlying device adapter.
            command (str): The name of the debug command to run.
            args (dict): Any command arguments.

        Returns:
            object: The response to the debug command.

        Raises:
            DeviceServerError: There is an issue with your client_id such
                as not being connected to the device.
            DeviceAdapterError: The adapter had a protocol issue sending the debug
                command.
        """

        conn_id = self._client_info(client_id, 'connections')[conn_string]
        return await self.adapter.debug(conn_id, command, args)

    def _adjust_global_events(self, client_id, scan=None, broadcast=None):
        monitor = self._client_info(client_id, 'monitor')

        action = {False: "remove", True: "add"}

        if scan is not None:
            self.adapter.adjust_monitor(monitor, action.get(scan), [None], ['device_seen'])

        if broadcast is not None:
            self.adapter.adjust_monitor(monitor, action.get(broadcast), [None], ['broadcast'])

    #pylint:disable=too-many-arguments;This is an internal utility method
    def _adjust_device_events(self, client_id, conn_string, report=None, trace=None, disconnect=None, progress=None):
        monitor = self._client_info(client_id, 'monitor')

        action = {False: "remove", True: "add"}

        if report is not None:
            self.adapter.adjust_monitor(monitor, action.get(report), [conn_string], ['report'])

        if trace is not None:
            self.adapter.adjust_monitor(monitor, action.get(trace), [conn_string], ['trace'])

        if disconnect is not None:
            self.adapter.adjust_monitor(monitor, action.get(disconnect), [conn_string], ['disconnection'])

        if progress is not None:
            self.adapter.adjust_monitor(monitor, action.get(disconnect), [conn_string], ['progress'])

    def _client_connection(self, client_id, conn_string):
        conns = self._client_info(client_id, 'connections')

        conn_id = conns.get(conn_string)
        if conn_id is None:
            raise DeviceServerError(client_id, conn_string, 'get_connection', 'client does not have connection')

        return conn_id

    def _client_info(self, client_id, key=None):
        client_info = self._clients.get(client_id)

        if client_info is None:
            raise DeviceServerError(client_id, None, 'get_client_info', "unknown client id")

        if key is None:
            return client_info

        return client_info[key]

    def _hook_connect(self, conn_string, conn_id, client_id):
        self._client_info(client_id, 'connections')[conn_string] = conn_id
        self._adjust_device_events(client_id, conn_string, disconnect=True, progress=True)

    def _hook_disconnect(self, conn_string, client_id):
        self._adjust_device_events(client_id, conn_string,
                                   disconnect=False, report=False, trace=False, progress=False)
        del self._client_info(client_id, 'connections')[conn_string]

    def _hook_open_interface(self, conn_string, interface, client_id):
        if interface == 'streaming':
            self._adjust_device_events(client_id, conn_string, report=True)
        elif interface == 'tracing':
            self._adjust_device_events(client_id, conn_string, trace=True)

    def _hook_close_interface(self, conn_string, interface, client_id):
        if interface == 'streaming':
            self._adjust_device_events(client_id, conn_string, report=False)
        elif interface == 'tracing':
            self._adjust_device_events(client_id, conn_string, trace=False)

    async def _forward_client_event(self, client_id, event_tuple):
        conn_string, name, _ = event_tuple
        user_data = self._client_info(client_id, 'user_data')

        if name == 'disconnect':
            self._hook_disconnect(conn_string, client_id)

        if self.client_event_handler is not None:
            result = self.client_event_handler(client_id, event_tuple, user_data=user_data)  #pylint:disable=assignment-from-none;This is an overridable method
            if inspect.isawaitable(result):
                await result
