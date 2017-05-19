import logging
import copy
import datetime
import tornado.ioloop
import tornado.gen
import uuid
from iotile.core.exceptions import ArgumentError


class DeviceManager(object):
    """An object to manage connections to IOTile devices over one or more specific DeviceAdapters.

    DeviceManagers aggregate all of the available devices across each DeviceAdapter and route
    connections to the appropriate adapter as connections are requested.  An API is provided
    to make connections to devices, monitor events that happen on devices and remember what
    devices have been seen on different adapters.

    It is assumed that devices have unique identifiers so if the same device is seen by multiple
    DeviceAdapters, those different instances are unified and the best route to the device is
    chosen when a user tries to connect to it.  For this purpose there is an abstract notion
    of 'signal_strength' that is reported by each DeviceAdapter and used to rank which one
    has a better route to a given device.

    Args:
        loop (tornado.ioloop.IOLoop): A tornado IOLoop object that this DeviceManager will run
            itself in.  It is up to the caller to make sure the loop is started and run.  The
            DeviceManager will run forever until the loop is stopped.
    """

    ConnectionIdleState = 0
    ConnectionRequestedState = 1
    ConnectedState = 3
    DisconnectionStartedState = 4
    DisconnectedState = 5

    def __init__(self, loop):
        self.monitors = {}
        self._scanned_devices = {}
        self.adapters = {}
        self.connections = {}
        self._loop = loop
        self._logger = logging.getLogger(__name__)
        self._logger.setLevel(logging.DEBUG)
        self._next_conn_id = 0

        tornado.ioloop.PeriodicCallback(self.device_expiry_callback, 1000, self._loop).start()

    def add_adapter(self, man):
        adapter_id = len(self.adapters)
        self.adapters[adapter_id] = man
        man.set_id(adapter_id)

        man.add_callback('on_scan', self.device_found_callback)
        man.add_callback('on_disconnect', self.device_disconnected_callback)
        man.add_callback('on_report', self.report_received_callback)
        man.add_callback('on_trace', self.trace_received_callback)

        # If this adapter supports probing for devices, probe now so we have an initial
        # list of connected devices without waiting for them to show up over time
        if man.get_config('probe_supported', False):
            man.probe_sync()

        tornado.ioloop.PeriodicCallback(man.periodic_callback, 1000, self._loop).start()

    def stop(self):
        """Stop all adapters managed by the DeviceManager
        """
        for _, adapter in self.adapters.iteritems():
            adapter.stop_sync()

    @property
    def scanned_devices(self):
        """Return a dictionary of all scanned devices across all connected DeviceAdapters

        Returns:
            dict: A dictionary mapping UUIDs to device information dictionaries
        """

        devs = {}

        for device_id, adapters in self._scanned_devices.iteritems():
            dev = None
            max_signal = None
            best_adapter = None

            for adapter_id, devinfo in adapters.iteritems():
                connstring = "{0}/{1}".format(adapter_id, devinfo['connection_string'])
                if dev is None:
                    dev = copy.deepcopy(devinfo)
                    del dev['connection_string']

                if 'adapters' not in dev:
                    dev['adapters'] = []
                    best_adapter = adapter_id

                dev['adapters'].append((adapter_id, devinfo['signal_strength'], connstring))

                if max_signal is None:
                    max_signal = devinfo['signal_strength']
                elif devinfo['signal_strength'] > max_signal:
                    max_signal = devinfo['signal_strength']
                    best_adapter = adapter_id

            # If device has been seen in no adapters, it will get expired
            # don't return it
            if dev is None:
                continue

            dev['adapters'] = sorted(dev['adapters'], key=lambda x: x[1], reverse=True)
            dev['best_adapter'] = best_adapter
            dev['signal_strength'] = max_signal

            devs[device_id] = dev

        return devs

    @tornado.gen.coroutine
    def connect(self, uuid):
        """Coroutine to attempt to connect to a device by its UUID

        Args:
            uuid (int): the IOTile UUID of the device that we're trying to connect to

        Returns:
            a dict containing:
                'success': bool with whether the attempt was sucessful
                'reason': failure_reason as a string if the attempt failed
                'connection_id': int with the id for the connection if the attempt was successful,
                'connection_string': a string that can be used to reconnect to this exact device in the
                    future on success
        """

        devs = self.scanned_devices

        if uuid not in devs:
            raise tornado.gen.Return({'success': False, 'reason': 'Could not find UUID'})

        adapter_id = None
        connection_string = None
        #Find the best adapter to use based on the first adapter with an open connection spot
        for adapter, signal, connstring in devs[uuid]['adapters']:
            if self.adapters[adapter].can_connect():
                adapter_id = adapter
                connection_string = connstring
                break

        if adapter_id is None:
            raise tornado.gen.Return({'success': False, 'reason': "No room on any adapter that sees this device for more connections"})

        result = yield self.connect_direct(connection_string)
        if result['success']:
            result['connection_string'] = connection_string
            conn_id = result['connection_id']
            self._update_connection_data(conn_id, 'uuid', uuid)

        raise tornado.gen.Return(result)

    def register_monitor(self, device_uuid, filter_names, callback):
        """Register to receive callbacks when events happen on a specific device

        The registered callback function will be called whenever the following events occur
        using the given event_name:
        - 'report': a report is received from the device
        - 'connection': someone has connected to the device
        - 'trace': tracing data has been received from a device
        - 'device_seen': a scan event has seen the device
        - 'disconnection': someone has disconnected from the device

        Args:
            device_uuid (int): The device that we want to monitor
            filter_name (iterable): A list of strings with the event names that the caller would wish
                to receive
            callback (callable): The function that should be called when an event occurs
                callback must have the signature callback(event_name, event_arg)

        Returns:
            string: A unique string that can be used to remove or adjust this monitoring callback in the future
        """

        # FIXME: Check filter_names to make sure they contain only supported event names

        monitor_uuid = uuid.uuid4()

        if device_uuid not in self.monitors:
            self.monitors[device_uuid] = {}

        self.monitors[device_uuid][monitor_uuid.hex] = (set(filter_names), callback)

        return "{}/{}".format(device_uuid, monitor_uuid.hex)

    def adjust_monitor(self, monitor_id, add_events=None, remove_events=None):
        """Adjust the events that this monitor wishes to receive

        Args:
            monitor_id (string): The exact string returned from a previous call to register_monitor
            add_events (iterable): A list of events to begin receiving
            remove_events (iterable): A list of events to stop receiving
        """

        dev_uuid, _, monitor_name = monitor_id.partition('/')
        dev_uuid = int(dev_uuid)
        if dev_uuid not in self.monitors or monitor_name not in self.monitors[dev_uuid]:
            raise ArgumentError("Could not find monitor by name", monitor_id=monitor_id)

        filters, callback = self.monitors[dev_uuid][monitor_name]

        if add_events is not None:
            filters.update(add_events)
        if remove_events is not None:
            filters.difference_update(remove_events)

        self.monitors[dev_uuid][monitor_name] = (filters, callback)

    def remove_monitor(self, monitor_id):
        """Remove a previously added device event monitro

        Args:
            monitor_id (string): The exact string returned from a previous call to register_monitor
        """

        dev_uuid, _, monitor_name = monitor_id.partition('/')
        dev_uuid = int(dev_uuid)

        if dev_uuid not in self.monitors or monitor_name not in self.monitors[dev_uuid]:
            raise ArgumentError("Could not find monitor by name", monitor_id=monitor_id)

        del self.monitors[dev_uuid][monitor_name]

    def call_monitor(self, device_uuid, event, *args):
        """Call a monitoring function for an event on device

        Args:
            device_uuid (int): The UUID of the device
            event (string): The name of the event
            *args: Arguments to be passed to the event monitor function
        """
        if device_uuid not in self.monitors:
            return

        for listeners, monitor in self.monitors[device_uuid].itervalues():
            if event in listeners:
                monitor(device_uuid, event, *args)

    @tornado.gen.coroutine
    def connect_direct(self, connection_string):
        """Directly connect to a device using its connection string

        Connection strings are opaque strings returned by DeviceAdapter objects that allow direct
        connection to a unique IOTile device accessible via that adapter.  The DeviceManager prepends
        an adapter id to the connection string, separating both with a '/' so that you can directly
        address any device on any DeviceAdapter using a combined connection_string.

        Args:
            connection_string (string): A connection string that specifies a combination of an adapter and
                a device on that adapter.

        Returns:
            a dict containing:
                'success': bool with whether the attempt was sucessful
                'reason': failure_reason as a string if the attempt failed
                'connection_id': int with the id for the connection if the attempt was successful
        """

        adapter_id, _, connstring = connection_string.partition('/')
        adapter_id = int(adapter_id)

        if adapter_id not in self.adapters:
            raise tornado.gen.Return({'success': False, 'reason': "Adapter ID not found in connection string"})

        conn_id = self._get_connection_id()
        self._update_connection_data(conn_id, 'adapter', adapter_id)
        self._update_connection_data(conn_id, 'report_callbacks', set())
        self._update_connection_state(conn_id, self.ConnectionRequestedState)

        result = yield tornado.gen.Task(self.adapters[adapter_id].connect_async, conn_id, connstring)
        conn_id, adapter_id, success, failure_reason = result.args

        resp = {}
        resp['success'] = success

        if success:
            self._update_connection_state(conn_id, self.ConnectedState)
            resp['connection_id'] = conn_id
        else:
            del self.connections[conn_id]
            if 'failure_reason' is not None:
                resp['reason'] = failure_reason
            else:
                resp['reason'] = 'Unknown failure reason'

        raise tornado.gen.Return(resp)

    @tornado.gen.coroutine
    def open_interface(self, connection_id, interface):
        """Coroutine to attempt to enable a particular interface on a connected device

        Args:
            connection_id (int): The id of a previously opened connection
            interface (string): The name of the interface that we are trying to enable

        Returns:
            a dictionary containg two keys:
                'success': bool with whether the attempt was sucessful
                'reason': failure_reason as a string if the attempt failed
        """

        if connection_id not in self.connections:
            raise tornado.gen.Return({'success': False, 'reason': 'Could not find connection id %d' % connection_id})

        adapter = self._get_connection_data(connection_id, 'adapter')

        result = yield tornado.gen.Task(self.adapters[adapter].open_interface_async, connection_id, interface)

        _, _, success, failure_reason = result.args

        resp = {}
        resp['success'] = success

        if not success:
            if 'failure_reason' is not None:
                resp['reason'] = failure_reason
            else:
                resp['reason'] = 'Unknown failure reason'

        raise tornado.gen.Return(resp)

    @tornado.gen.coroutine
    def close_interface(self, connection_id, interface):
        """Coroutine to attempt to disable a particular interface on a connected device

        Args:
            connection_id (int): The id of a previously opened connection
            interface (string): The name of the interface that we are trying to disable

        Returns:
            a dictionary containg two keys:
                'success': bool with whether the attempt was sucessful
                'reason': failure_reason as a string if the attempt failed
        """

        if connection_id not in self.connections:
            raise tornado.gen.Return({'success': False, 'reason': 'Could not find connection id %d' % connection_id})

        adapter = self._get_connection_data(connection_id, 'adapter')

        result = yield tornado.gen.Task(self.adapters[adapter].close_interface_async, connection_id, interface)

        _, _, success, failure_reason = result.args

        resp = {}
        resp['success'] = success

        if not success:
            if 'failure_reason' is not None:
                resp['reason'] = failure_reason
            else:
                resp['reason'] = 'Unknown failure reason'

        raise tornado.gen.Return(resp)

    @tornado.gen.coroutine
    def disconnect(self, connection_id):
        """Disconnect from a current connection

        Args:
            connection_id (int): The connection id returned from a previous call to connect()

        Returns:
            a dictionary containing two keys:
                'success': bool with whether the attempt was sucessful
                'reason': failure_reason as a string if the attempt failed
        """

        if connection_id not in self.connections:
            raise tornado.gen.Return({'success': False, 'reason': 'Could not find connection id %d' % connection_id})

        if self.connections[connection_id]['state'] != self.ConnectedState:
            raise tornado.gen.Return({'success': False, 'reason': 'Connection id %d is not in the right state' % connection_id})

        adapter_id = self.connections[connection_id]['context']['adapter']

        result = yield tornado.gen.Task(self.adapters[adapter_id].disconnect_async, connection_id)
        _, _, success, failure_reason = result.args

        resp = {}
        resp['success'] = success

        if success:
            del self.connections[connection_id]
        else:
            if 'failure_reason' is not None:
                resp['reason'] = failure_reason
            else:
                resp['reason'] = 'Unknown failure reason'

        raise tornado.gen.Return(resp)

    @tornado.gen.coroutine
    def send_rpc(self, connection_id, address, feature, command, payload, timeout):
        """Send an RPC to an IOTile device

        Args:
            connection_id (int): The connection id returned from a previous call to connect()
            address (int): the address of the tile that you want to talk to
            feature (int): the high byte of the rpc id
            command (int): the low byte of the rpc id
            payload (string): the payload to send (up to 20 bytes)
            timeout (float): the maximum amount of time to wait for a response
        """

        if connection_id not in self.connections:
            raise tornado.gen.Return({'success': False, 'reason': 'Could not find connection id %d' % connection_id})

        if self.connections[connection_id]['state'] != self.ConnectedState:
            raise tornado.gen.Return({'success': False, 'reason': 'Connection id %d is not in the right state' % connection_id})

        rpc_id = (feature << 8) | command
        adapter_id = self.connections[connection_id]['context']['adapter']
        result = yield tornado.gen.Task(self.adapters[adapter_id].send_rpc_async, connection_id, address, rpc_id, payload, timeout)
        _, _, success, failure_reason, status, payload = result.args

        resp = {}
        resp['success'] = success

        if success:
            resp['status'] = status
            resp['payload'] = str(payload)
        else:
            resp['reason'] = failure_reason

        raise tornado.gen.Return(resp)

    @tornado.gen.coroutine
    def send_script(self, connection_id, data, progress_callback):
        """
        """

        if connection_id not in self.connections:
            raise tornado.gen.Return({'success': False, 'reason': 'Could not find connection id %d' % connection_id})

        if self.connections[connection_id]['state'] != self.ConnectedState:
            raise tornado.gen.Return({'success': False, 'reason': 'Connection id %d is not in the right state' % connection_id})

        adapter_id = self.connections[connection_id]['context']['adapter']
        result = yield tornado.gen.Task(self.adapters[adapter_id].send_script_async, connection_id, data, progress_callback)
        _, _, success, failure_reason = result.args

        resp = {}
        resp['success'] = success

        if not success:
            resp['reason'] = failure_reason

        raise tornado.gen.Return(resp)

    def _get_connection_id(self):
        """Get a unique connection ID

        Returns:
            int: the unique id for this connection
        """

        next_id = self._next_conn_id
        self._next_conn_id += 1

        self.connections[next_id] = {'state': self.ConnectionIdleState, 'context': {}}
        return next_id

    def _update_connection_data(self, conn_id, key, value):
        if conn_id not in self.connections:
            raise ValueError("Unknown conn_id")

        self.connections[conn_id]['context'][key] = value

    def _get_connection_data(self, conn_id, key):
        if conn_id not in self.connections:
            raise ValueError("Unknown conn_id")

        return self.connections[conn_id]['context'][key]

    def _update_connection_state(self, conn_id, new_state):
        """Update the connection state for this connection

        Args:
            conn_id (int): The connection ID to update
            new_state: The new state to transition into
        """

        if conn_id not in self.connections:
            raise ValueError("Unknown conn_id")

        self.connections[conn_id]['state'] = new_state

    def _get_connection_string(self, uuid, adapter_id):
        """Return the connection string appropriate to connect to a device using a given adapter

        Returns:
            string: the appropriate connection string that can be passed to the given adapter to
                connect to this device.
        """

        devs = self._scanned_devices

        return devs[uuid][adapter_id]['connection_string']

    def device_disconnected_callback(self, adapter, connection_id):
        """Called when an adapter has had an unexpected device disconnection

        Args:
            adapter (int): The id of the adapter that was disconnected
            connection_id (int): The id of the connection that has been disconnected
        """

        def sync_device_disconnected_callback(self, adapter, connection_id):
            pass

        self._loop.add_callback(sync_device_disconnected_callback, self, adapter, connection_id)

    def device_found_callback(self, ad, inf, exp):
        """Add or update a device record in scanned_devices

        This notification function is called by a DeviceAdapter and notifies the device manager
        that a new device has been seen.

        This callback must only be called on the main tornado ioloop.

        Args:
            adapter (int): the id of the adapter that found this device
            info (dict): a dictionary of information about the device including its uuid
            expires (int): the number of seconds the device should stay in scanned_devices before expiring.
                If expires==0 then the record will never expire on its own,
        """

        def sync_device_found_callback(self, adapter, info, expires):
            uuid = info['uuid']

            if expires > 0:
                info['expires'] = datetime.datetime.now() + datetime.timedelta(seconds=expires)

            if uuid not in self._scanned_devices:
                self._scanned_devices[uuid] = {}

            devrecord = self._scanned_devices[uuid]
            devrecord[adapter] = info

        self._loop.add_callback(sync_device_found_callback, self, ad, inf, exp)

    def device_lost_callback(self, adapter, uuid):
        """Remove a device record from scanned_devices

        DeviceAdapters should call this function when they lose track of an IOTile device.
        This function SHOULD NOT be called when a device just hasn't been seen for awhile
        unless the DeviceAdapter knows that it is no longer accessible.

        This function should be useful only for DeviceAdapter objects that do not periodically
        scan for device where the natural expiration logic in DeviceManager would remove them,
        but rather know explicitly when devices come and go so they provide non-expiring records
        in device_found_callback

        Args:
            adapter (int): the id of the adapter that lost this device
            uuid (int): the UUID of the device to expire.
        """

        if uuid not in self._scanned_devices:
            self._logger.warn('Device lost called for UUID %d but device was not in scanned_devices list', uuid)
            return

        devrecord = self._scanned_devices[uuid]
        if adapter not in devrecord:
            self._logger.warn('Device lost called for UUID %d but device was not registered for the adapter that lost it (adapter id=%d)', adapter, uuid)
            return

        del devrecord[adapter]

    def trace_received_callback(self, connection_id, trace):
        """Callback when tracing data has been received for a connection

        Args:
            connection_id (int): The id of the connection for which the report was received
            trace (bytearray): The raw data traced from the device
        """

        def sync_trace_received_callback(self, connection_id, report):
            if connection_id not in self.connections:
                self._logger.warn('Dropping tracing data for an unknown connection %d', connection_id)

            try:
                dev_uuid = self._get_connection_data(connection_id, 'uuid')
                self.call_monitor(dev_uuid, 'trace', report)
            except KeyError:
                self._logger.warn('Dropping tracing data for a connection that has no associated UUID %d', connection_id)

        self._loop.add_callback(sync_trace_received_callback, self, connection_id, trace)

    def report_received_callback(self, connection_id, report):
        """Callback when a report has been received for a connection

        Args:
            connection_id (int): The id of the connection for which the report was received
            report (IOTileReport): A report streamed from a device
        """

        def sync_reported_received_callback(self, connection_id, report):
            if connection_id not in self.connections:
                self._logger.warn('Dropping report for an unknown connection %d', connection_id)

            try:
                dev_uuid = self._get_connection_data(connection_id, 'uuid')
                self.call_monitor(dev_uuid, 'report', report)
            except KeyError:
                self._logger.warn('Dropping report for a connection that has no associated UUID %d', connection_id)

        self._loop.add_callback(sync_reported_received_callback, self, connection_id, report)

    def device_expiry_callback(self):
        """Periodic callback to remove expired devices from scanned_devices list
        """

        expired = 0
        for uuid, adapters in self._scanned_devices.iteritems():
            to_remove = []
            now = datetime.datetime.now()

            for adapter, dev in adapters.iteritems():
                if 'expires' not in dev:
                    continue

                if now > dev['expires']:
                    to_remove.append(adapter)

            for x in to_remove:
                del adapters[x]
                expired += 1

        if expired > 0:
            self._logger.info('Expired %d devices' % expired)
