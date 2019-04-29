"""Abstract base class for modern coroutine based DeviceAdapters.

All modern DeviceAdapter subclasses must implement this interface. This class
is the core interface by which any software built on top of CoreTools
interacts with an IOTile device.

High Level
==========

At a basic level, communication with an IOTile device through a DeviceAdapter
is connection oriented.  You connect to a device, then you open an interface
on that device.  You can then use that interface to interact with the device.
You close the interface when you are done and then you disconnect from the
device.


Implementation Details
----------------------

It is a very conscious choice to specify that :class:AbstractDeviceAdapter
must implement many of its methods as coroutines.  This is the product of much
experience implementing this functionality without coroutines and seeing the
complexity that it introduces into the internal implementation of a
DeviceAdapter.

Previous DeviceAdapter implementations used multithreading and callback based
interfaces that worked but proved difficult to implement, raising the barrier
to creating new DeviceAdapters to support additional communication protocols.


Events
======

Communication with a device through an AbstractDeviceAdapter is bidrectional
in that commands can flow from the user to the device and events can flow
back from the devie to the user without being the direct result of a command.

The way to receive events is to register an event monitor using
:meth:`AbstractDeviceAdapter.register_monitor`.  There are different kinds of
events that you can receive and your monitor includes filters based on the
event name and the source device.

Every event notification contains a tuple with three things: the connection
string of the device that sent the event, the name of the event and an event
object whose contents vary depending on the event name.  The supported events
are:

    report
        A report has been received from the device.

        The event object will be a subclass of
        :class:`iotile.core.hw.reports.IOTileReport`.
        This event is used to send reports from a device to the user via the
        streaming interface.  It can only be received if the streaming
        interface is open.

    connection
        Someone has connected to a device.

        The event object for this event will be ``None`` since there is not
        additional information available.

    trace
        Tracing data has been received from a device.

        The event object will be a ``bytes`` object containing a blob of
        tracing data.  Since tracing data may be fragmented as it travels from
        the device to you, there is no guarantee that you will receive it in
        the same atomic chunk sizes that the device sent.  In particular,
        trace data may be temporarily buffered inside some device adapters for
        performance reasons.

    device_seen
        A scan event has been received for a device.

        The event object will be a dictionary with certain mandatory keys and
        perhaps some additional keys whose meaning is determined by the device
        adapter itself.

    disconnection
        Someone has disconnected from a device.

        The event object will be a dictionary with at least a single key
        ``reason`` set that will be a string that describes why the disconnect
        occurred.  There will additionally be an ``expected`` key, which will
        be a boolean and set to True if the disconnetion event is expected
        because it was the result of a call to the
        :meth:`AbstractDeviceAdapter.disconnect`` method.

    broadcast
        A broadcast report has been received from a device.

        The event object will be a subclass of
        :class:`iotile.core.hw.reports.BroadcastReport`

    progress
        A progress update has been received from a device.

        Progress events help update the user on the sate of a long-running
        task.  This may be received either from a debug operation or a sending
        a script.

        The event object will be a dict with three keys set:

            operation
                The string name of the operation in progress: either ``script`` or
                ``debug``
            finished
                An integer specifying how many operation steps have finished.
            total
                An integer specifying how many total operation steps there are.
"""

import abc


class AbstractDeviceAdapter(abc.ABC):
    """The base class for all modern DeviceAdapters.

    This abstract class contains the interface that all DeviceAdapter classes
    must implement.  Any class implementing this interface can be used by
    CoreTools in order to interact with IOTile devices.  All hardware interaction
    in CoreTools is built on top of this foundation.

    Note that many of the methods in this class are specified to be
    implemented as coroutines. This is very important to allow for simple
    cooperative-multitasking around the typically long-running network
    communications required to perform operations on remote IOTile devices.
    """

    @abc.abstractmethod
    def can_connect(self):
        """Return whether this device adapter can accept another connection.

        Depending on the underlying hardware and transport protocols in use, a
        given DeviceAdapter may be able to maintain simultaneous connections
        to more than one device at a time.  In simple cases, this method is
        not necessary because a user can just try to connect to a device and
        have it fail if the adapter cannot accomodate another connection.

        However, in more complicated scenarios where there are multiple
        DeviceAdapters that could be used to connect to a device, it is useful
        to be able to filter them and find the best adapter that has a free
        connection slot available.

        Returns:
            bool: Whether one additional connection is possible
        """

    @abc.abstractmethod
    def get_config(self, name, default):
        """Get a configuration setting from this DeviceAdapter.

        This command can be used query features a DeviceAdapter supports
        before calling ``start`` to turn it on.  The list of keys that you can
        pass to ``name`` will be DeviceAdapter specific.

        This method is safe to call before ``start`` is called.  The
        DeviceAdapter will typically set many config values itself in its
        constructor that you can query with this method.

        Args:
            name (str): The name of the parameter to set
            default (object): The default value to return.  If no default is
                specified and the config parameter was never set an
                Exception will be raised.

        Raises:
            ArgumentError: The config does not exist and no default was specified.
        """

    @abc.abstractmethod
    def set_config(self, name, value):
        """Adjust a configuration setting on this DeviceAdapter.

        This command can be used to adjust how a DeviceAdapter will work
        before calling ``start`` to turn it on.  The list of keys that you can
        pass to ``name`` will be DeviceAdapter specific.

        This method is safe to call before ``start`` is called.  The
        DeviceAdapter will typically set many config values itself in its
        constructor that you are able to override in this method.

        Args:
            name (str): The name of the parameter to set
            value (object): The new value.
        """

    @abc.abstractmethod
    def register_monitor(self, devices, events, callback):
        """Register a callback when events happen.

        This method allows you to setup callbacks when events of interest
        happen inside of the device adapter.  You can register as many
        callbacks as you want and install filters for them to only receive a
        subset of events based on which device is involved or what kind of
        event it is.

        The supported event names are:

            report
                A report is received from the device.
            connection
                Someone has connected to a device.
            trace
                Tracing data has been received from a device.
            device_seen
                A scan event has been received for a device.
            disconnection
                Someone has disconnected from a device.
            broadcast
                A broadcast report has been received from a device.
            progress
                A progress update has been received from a device
                performing a long-running task.  This may be received
                either from a debug operation or a sending a script.

        The ``devices`` are a set of connection_string objects containing
        which devices you want to install this filter on.  All events are tied
        to a single device.  You can install a monitor to monitor a single
        device or all devices but keep in mind the volume of events you will
        get passed if installing a global monitor when there are many devices
        nearby.

        Coroutine callbacks are supported and will be awaited after each
        event.  Keep this in mind if your coroutine is long-running since it
        may block internal notification queues.

        All callbacks registered through this mechanism will be called in the
        following way::

            callback(conn_string, conn_id, event_name, event_object)

        The connection string will never be None but conn_id may be None for
        events that are associated with a device that does not have an active
        connection on this adapter.

        .. important:

            Once the adapter has started, this method may only be called from
            within the same event loop that is sending notification callbacks.
            All subclasses must ensure that this method works when called from
            within a notification callback itself.

        Args:
            devices (iterable of str): The devices, identified by their
                connection_string that you want to receive events for.  If you
                pass None here then all devices will be selected.
            events (iterable of str): The event names that you wish to register
                the callback for.
            callback (callable): The callback that should be invoked when an
                event happens.  If the callback is a coroutine function it
                will be awaited after each event.

        Raises:
            ArgumentError: The event name is unknown or the filters are invalid.

        Returns:
            object: A handle that can be used to adjust or remove the monitor.
        """

    @abc.abstractmethod
    def unique_conn_id(self):
        """Generate a new unique connection id.

        This method allows DeviceAdapters to tell their clients what they
        should pick for a connection id to ensure that it does not conflict
        with any current connection.  This can be imlemented as a simple
        incrementing counter, so clients must not mix calling unique_conn_id
        with setting their own connection ids.

        This method is very important when there could be multiple users
        connected to the same AbstractDeviceAdapter and they need to ensure
        that they don't accidentally pick the same connection id.

        Returns:
            int: A new, unique integer suitable for use as a conn_id.
        """

    @abc.abstractmethod
    def adjust_monitor(self, handle, action, devices, events):
        """Adjust a previously registered callback.

        This method allows you to adjust what events are listened for by a
        previously registered monitor or what devices are selected to receive
        events from.

        See :meth:`register_monitor` for the list of supported event names.

        If you remove a device or event that was not previously registered, no
        error is raised.  Similarly, if you add an event that was already
        registered, no error is raised.  The ``adjust_monitor`` method is
        idempotent.

        Args:
            handle (object): The handle to a previously registered monitor.
            action (str): One of ``add`` or ``remove``.
            devices (iterable of str): The devices that we wish to impact.
            events (iterable of str): The events that we wish to add or remove.

        Raises:
            ArgumentError: ``handle`` is not a registered monitor.
        """

    @abc.abstractmethod
    def remove_monitor(self, handle):
        """Remove a previously registered monitor.

        This method is idempotent so if the monitor does not exist, nothing
        occurs and no error is raised.

        Args:
            handle (object): The handle to a previously registered monitor.
        """

    @abc.abstractmethod
    async def probe(self):
        """Probe for visible devices connected to this DeviceAdapter.

        There are two ways by which a user could discover that they could
        connect to a device through the DeviceAdapter:

        1. The device could advertise itself periodically and the user could
           wait until they receive an ``on_found`` callback the next time the
           device adverises.

        2. There could be a mechanism to scan or probe for all connectable
           devices.  Not all DeviceAdapters are cabable of probing, but for
           those that are, it will ensure that ``on_found`` is called for any
           nearby connectable devices before returning.

        DeviceAdapter classes that can only find devices when explicitly
        searching for them should implement this method.  The method itself
        doesn't return anything but it should have a side effect that triggers
        ``on_found`` callbacks for any connectable devices.
        """

    @abc.abstractmethod
    async def connect(self, conn_id, connection_string):
        """Connect to a device.

        This coroutine should connect to a device using the passed connection
        string.  If the connection is succesful, this method returns nothing.
        If it fails, this method must raise a DeviceAdapterError exception
        that contains the reason for the failure.

        The ``conn_id`` parameter is an arbitrary unique integer passed in by
        the caller to identify the connection.  If connect() succeeds, then
        all future interaction with this device (while still connected) will
        reference ``conn_id`` as a pointer to this device.

        ``connection_string`` is an opaque str object that has meaning to
        this DeviceAdapter and lets it uniquely identify and connect to an
        IOTile Device.  These strings are always generated, originally,
        from the DeviceAdapter itself and sent to the user via ``on_found``
        callbacks when devices are observed nearby, or during a probe
        operation.

        The user calling this method does not necessarily know what the
        ``connection_string`` means that they are passing.  It is just an
        opaque token that this DeviceAdapter previously gave to the user to
        identify a connectable device.

        This means that before calling ``connect``, most users will need to
        have previously called ``probe`` to obtain a valid connection_string
        or registered an ``on_found`` event callback and waited a sufficient
        time for the callback to be called.

        Note that it is not required that only connection_strings returned
        from a prior ``on_found`` callback be passed to ``connect``.  If the
        connection_string has a semantic format that the user understands,
        e.g. it is a MAC address, then the user can try to connect to a device
        directly, without a discovery process, by constructing the appropriate
        connection_string manually.

        Args:
            conn_id (int): A unique identifier that will refer to this connection.
                The caller chooses this and it must be unique among all active
                connections but otherwise arbitrary.
            connection_string (str): A DeviceAdapter specific string that can be used
                to identify a connectable device.  The caller typically obtains this
                string by listening for ``on_found`` notifications or using the
                ``probe`` method.

        Raises:
            DeviceAdapterError: If the connection attempt was unsuccessful
        """

    @abc.abstractmethod
    async def disconnect(self, conn_id):
        """Disconnect from a connected device.

        This method will cleanly disconnect the given device and free any
        resources reserved for it on this DeviceAdapter.  It may only be
        called after a previous call to ``connect`` has succeeded and must be
        passed the same ``conn_id`` parameter in order to identify the
        appropriate device to disconnect from.

        Args:
            conn_id (int): The conn_id passed to a previously successful
                call to connect.

        Raises:
            DeviceAdapterError: The disconnection attempt was unsuccessful
        """

    @abc.abstractmethod
    async def open_interface(self, conn_id, interface):
        """Open an interface on a connected device.

        All interactions with a device through a DeviceAdapter happen
        on an interface.  There are different kinds of interfaces and
        they have different operations that they support.  The five
        kinds of interfaces are:

            rpc
                This interface allows you to send a synchronous command
                to the device and get a response like calling a function
                or invoking a shell command.

            script
                This interface allows you to send a multicommand script
                to the device at high speed, which will be stored and
                may be triggered to run at a later point using an rpc.

            streaming
                This interface is unidirectional from the device to the
                user and allows it to send universally understandable
                data reports that contain timestamped sensor or other
                readings.

            tracing
                This is a unidirectional socket-like interface from the
                device to the user that can be used to send arbitary
                binary data.

            debug
                This is a debugging interface that can be used to send
                out-of-band commands to the device or associated debug
                circuitry around it such as manually reflashing its
                firmware, inspecting its memory etc.

        Not all devices implement all 5 interfaces, nor do all DeviceAdapters.
        You must open an interface before you are able to use it (and you
        should close it when you done).  What actual physical actions are
        performed when you "open an interface" are unspecified and vary widely
        from DeviceAdapter to DeviceAdapter based on the needs of the
        underlying communication protocol.

        You must be connected to a device before you can open an interface on
        it.

        Args:
            interface (str): The interface to open.  This must be one of the
                following strings: ``rpc``, ``script``, ``streaming``, ``tracing``,
                ``debug``.
            conn_id (int): The connection id used in a previous successful call
                to ``connect``.

        Raises:
            DeviceAdapterError: The interface could not be opened.
        """

    @abc.abstractmethod
    async def close_interface(self, conn_id, interface):
        """Close an interface on a device.

        The interface parameter must be one of (rpc, script, streaming,
        tracing, debug).  You must hvae previously opened the interface
        using ``open_interface`` for this call to succeed.

        Args:
            interface (string): The interface to close
            conn_id (int): The connection id used in a previous successful call
                to ``connect``.

        Raises:
            DeviceAdapterError: The interface could not be closed.
        """

    @abc.abstractmethod
    async def send_rpc(self, conn_id, address, rpc_id, payload, timeout):
        """Send an RPC to a device.

        This method is the only way to interact with the RPC interface of a
        device.  You specify two numbers: ``address`` and ``rpc_id`` that
        uniquely identify a remotely callable procedure inside the device and
        pass a payload containing the marshalled command arguments.

        The procedure is invoked and its return value is marshalled and sent
        back to you as a binary blob.

        You can specify a timeout for the maximum amount of time you expect
        the RPC to take so that DeviceAdapter can set an appropriate internal
        timeout to protect against communication failures while not failing
        too soon if the RPC is known to be long-running.

        The exact meaning and size of ``address`` and ``rpc_id`` are technically
        specified by the device itself but most DeviceAdapters and devices
        enforce the following limits:

        - address: 1 bytes
        - rpc_id: 2 bytes
        - payload: up to 20 bytes
        - response: up to 20 bytes

        The combination of ``address`` and ``rpc_id`` must uniquely identify a
        single RPC implementation on the device.  It is not required that
        ``rpc_id`` itself is unique.

        Args:
            conn_id (int): A unique identifier that will refer to this connection
            address (int): the addres of the tile that we wish to send the RPC to
            rpc_id (int): the numerical id of the RPC we want to call
            payload (bytes): the payload of the command
            timeout (float): the number of seconds to wait for the RPC to execute

        Returns:
            bytes: The response payload returned by the RPC.

        Raises:
            TileNotFoundError: The destination tile address does not exist
            RPCNotFoundError: The rpc_id does not exist on the given tile
            RPCErrorCode: The RPC implementation wishes to fail with a
                non-zero status code.
            RPCInvalidIDError: The rpc_id is too large to fit in 16-bits.
            TileBusyError: The tile was busy and could not respond to the RPC.
            Exception: The rpc raised an exception during processing.
            DeviceAdapterError: If there is a hardware or communication issue
                invoking the RPC.
        """

    @abc.abstractmethod
    async def debug(self, conn_id, name, cmd_args):
        """Send a debug command to a device.

        The command name and arguments are passed to the underlying device
        adapter and interpreted there.  If the command is long running,
        you may receive progress events (if you have a registered event monitor).

        Most DeviceAdapter classes do not support this command or the debug
        interface since it typically requires a special hardware connection to
        the device.  However, for those that do, this method provides helpful
        debug related features.

        Args:
            conn_id (int): A unique identifier that will refer to this connection
            name (str): The name of the debug command we want to invoke
            cmd_args (dict): Any arguments that we want to send with this command.
        """

    @abc.abstractmethod
    async def send_script(self, conn_id, data):
        """Send a a script to a device.

        Scripts are like binary files transferred to a device.  They are
        typically used to perform atomic device updates.

        The device must have previously been connected to and you must have
        opened the script interface.  This method will robustly transfer a binary
        script blob to the device via its script interface and may inform you
        of its progress using progress events.

        Args:
            conn_id (int): A unique identifier specifying the connection
            data (bytes): The script to send to the device
        """

    @abc.abstractmethod
    async def start(self):
        """Start this AsyncDeviceAdapter.

        This method may only be called once in a DeviceAdapter's life and it
        will start any background activity that is needed and prepare the
        device adapter to function.  No other methods should be called before
        start() is called, except for ``get_config`` and ``set_config`` in
        order to perform any necessary adjustments.
        """

    @abc.abstractmethod
    async def stop(self):
        """Stop this AsyncDeviceAdapter.

        This method may only be called once in an AsyncDeviceAdapter's life
        and it will stop all background activity and free all resources
        associated with the DeviceAdapter.  No other calls should be made to
        the device adapter after stop() is called.
        """
