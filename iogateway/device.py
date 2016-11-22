import logging
import copy
import datetime
import tornado.ioloop
import tornado.gen
from tornado.concurrent import Future

class DeviceManager(object):
    """An object to manage connections to IOTile devices over one or more specific DeviceAdapters
    
    DeviceManagers aggregate all of the available devices across each DeviceAdapter and route 
    connections to the appropriate adapter as connections are requested.
    """

    ConnectionIdleState = 0
    ConnectionRequestedState = 1
    ConnectedState = 3
    DisconnectionStartedState = 4
    DisconnectedState = 5

    def __init__(self, loop):
        self._scanned_devices = {}
        self.adapters = {}
        self.connections = {}
        self._loop = loop
        self._logger = logging.getLogger('device.manager')
        self._next_conn_id = 0

        tornado.ioloop.PeriodicCallback(self.device_expiry_callback, 1000, self._loop).start()

    def add_adapter(self, man):
        adapter_id = len(self.adapters)
        self.adapters[adapter_id] = man
        man.set_id(adapter_id)

        man.add_callback('on_scan', self.device_found_callback)
        man.add_callback('on_disconnect', self.device_disconnected_callback)
        tornado.ioloop.PeriodicCallback(man.periodic_callback, 1000, self._loop).start()

    def stop(self):
        for adapter_id, adapter in self.adapters.iteritems():
            adapter.stop()

    @property
    def scanned_devices(self):
        """Return a dictionary of all scanned devices across all connected DeviceAdapters

        Returns:
            dict: A dictionary mapping UUIDs to device information dictionaries
        """

        devs = {}

        for uuid, adapters in self._scanned_devices.iteritems():
            dev = None
            max_signal = None
            best_adapter = None

            for adapter_id, devinfo in adapters.iteritems():
                if dev is None:
                    dev = copy.deepcopy(devinfo)

                if 'adapters' not in dev:
                    dev['adapters'] = [(adapter_id, devinfo['signal_strength'])]
                    best_adapter = adapter_id
                else:
                    dev['adapters'].append((adapter_id, devinfo['signal_strength']))

                if max_signal is None:
                    max_signal = devinfo['signal_strength']
                elif devinfo['signal_strength'] > max_signal:
                    max_signal = devinfo['signal_strength']
                    best_adapter = adapter_id

            #If device has been seen in no adapters, it will get expired
            #don't return it
            if dev is None:
                continue

            dev['adapters'] = sorted(dev['adapters'], key=lambda x: x[1], reverse=True)
            dev['best_adapter'] = best_adapter
            dev['signal_strength'] = max_signal

            devs[uuid] = dev

        return devs

    @tornado.gen.coroutine
    def connect(self, uuid):
        """Coroutine to attempt to connect to a device by its UUID

        Args:
            uuid (uuid): the IOTile UUID of the device that we're trying to connect to

        Returns:
            a dictionary containg two keys: 
                'success': bool with whether the attempt was sucessful
                'reason': failure_reason as a string if the attempt failed
                'connection_id': int with the id for the connection if the attempt was successful
        """

        devs = self.scanned_devices

        if uuid not in devs:
            raise tornado.gen.Return({'success': False, 'reason': 'Could not find UUID'})
            

        adapter_id = None
        #Find the best adapter to use based on the first adapter with an open connection spot
        for adapter, signal in devs[uuid]['adapters']:
            if self.adapters[adapter].can_connect():
                adapter_id = adapter
                break

        if adapter_id is None:
            raise tornado.gen.Return({'success': False, 'reason': "No room on any adapter that sees this device for more connections"})

        conn_id = self._get_connection_id()
        self._logger.info('UUID found, starting connection process (assigned id: %d)', conn_id)

        connstring = self._get_connection_string(uuid, adapter_id)

        self._update_connection_data(conn_id, 'adapter', adapter_id)
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
