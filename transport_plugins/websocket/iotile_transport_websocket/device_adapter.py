import logging
from builtins import range
from iotile.core.hw.transport.adapter import DeviceAdapter
from iotile.core.utilities.validating_wsclient import ValidatingWSClient
from iotile.core.hw.reports.parser import IOTileReportParser
from iotile.core.exceptions import ArgumentError, HardwareError
from connection_manager import ConnectionManager
from iotile.core.utilities.schema_verify import Verifier, DictionaryVerifier, LiteralVerifier, IntVerifier

ReportSchema = DictionaryVerifier()
ReportSchema.add_required('type', LiteralVerifier('report'))
ReportSchema.add_required('payload', Verifier())

TraceSchema = DictionaryVerifier()
TraceSchema.add_required('type', LiteralVerifier('trace'))
TraceSchema.add_required('payload', Verifier())

ProgressNotification = DictionaryVerifier()
ProgressNotification.add_required('type', LiteralVerifier('notification'))
ProgressNotification.add_required('operation', LiteralVerifier('send_script'))
ProgressNotification.add_required('connection_id', IntVerifier())
ProgressNotification.add_required('done_count', IntVerifier())
ProgressNotification.add_required('total_count', IntVerifier())


class WebSocketDeviceAdapter(DeviceAdapter):
    """ A device adapter allowing connections to devices over websockets

    Args:
        port (string): A url for the websocket server in form of server:port/path
    """

    def __init__(self, port):
        super(WebSocketDeviceAdapter, self).__init__()

        self.set_config('default_timeout', 10.0)
        self.set_config('expiration_time', 60.0)
        self.set_config('probe_supported', True)
        self.set_config('probe_required', True)
        self.mtu = int(self.get_config('mtu', 60*1024))  # Split script payloads larger than this

        self.logger = logging.getLogger('ws.manager')
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(logging.NullHandler())

        self.parser = IOTileReportParser(report_callback=self._on_report, error_callback=self._on_report_error)

        path = "ws://{0}/iotile/v2".format(port)
        self.client = ValidatingWSClient(path)
        self.client.add_message_type(ReportSchema, self.on_report_chunk_received)
        self.client.add_message_type(TraceSchema, self.on_trace_chunk_received)
        self.client.add_message_type(ProgressNotification, self.on_progress_script)
        self.client.start()

        self.connections = ConnectionManager(self.id)
        self.connections.start()

    def connect_async(self, connection_id, connection_string, callback):
        """Connect to a device by its connection_string

        Args:
            connection_id (int): A unique integer set by the caller for referring to this connection
                once created
            connection_string (string): A device id of the form d--XXXX-YYYY-ZZZZ-WWWW
            callback (callable): A callback function called when the connection has succeeded or
                failed
        """

        context = {}
        self.connections.begin_connection(
            connection_id,
            connection_string,
            callback,
            context,
            self.get_config('default_timeout')
        )

        try:
            result = self.client.send_command('connect', {})
        except Exception as err:
            reason = "Error while sending command 'connect' to ws server: {}".format(err)
            self.connections.finish_connection(connection_id, False, reason)
            raise HardwareError(reason)

        # FIXME: async after creating WebSocketHandler2
        self.connections.finish_connection(connection_id, result['success'], result.get('reason', None))

    def disconnect_async(self, connection_id, callback):
        """Asynchronously disconnect from a device that has previously been connected

        Args:
            connection_id (int): a unique identifier for this connection on the DeviceManager
                that owns this adapter.
            callback (callable): A function called as callback(connection_id, adapter_id, success, failure_reason)
            when the disconnection finishes.  Disconnection can only either succeed or timeout.
        """

        try:
            self.connections.get_connection_id(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        self.connections.begin_disconnection(connection_id, callback, self.get_config('default_timeout'))

        try:
            result = self.client.send_command('disconnect', {})
        except Exception as err:
            reason = "Error while sending command 'disconnect' to ws server: {}".format(err)
            self.connections.finish_disconnection(connection_id, False, reason)
            raise HardwareError(reason)

        # FIXME: async after creating WebSocketHandler2
        self.connections.finish_disconnection(connection_id, result['success'], result.get('reason', None))

    def probe_async(self, callback):
        """Probe for visible devices connected to this DeviceAdapter.

        Args:
            callback (callable): A callback for when the probe operation has completed.
                callback should have signature callback(adapter_id, success, failure_reason) where:
                    success: bool
                    failure_reason: None if success is True, otherwise a reason for why we could not probe
        """

        try:
            result = self.client.send_command('scan', {})
        except Exception as err:
            reason = "Error while sending command 'scan' to ws server: {}".format(err)
            raise HardwareError(reason)

        # FIXME: async after creating WebSocketHandler2
        payload = result.get('payload', None)
        if payload is not None:
            for dev in payload.get('devices', []):
                self._trigger_callback('on_scan', self.id, dev, self.get_config('expiration_time'))

        callback(self.id, result.get('success', False), result.get('reason', None))

    def stop_sync(self):
        """Synchronously stop this adapter
        """

        connections = self.connections.get_connections()

        for connection in connections:
            try:
                self.disconnect_sync(connection)
            except HardwareError:
                pass

        self.client.stop()
        self.connections.stop()

    def send_rpc_async(self, connection_id, address, rpc_id, payload, timeout, callback):
        """Asynchronously send an RPC to this IOTile device

        Args:
            connection_id (int): A unique identifier that will refer to this connection
            address (int): the address of the tile that we wish to send the RPC to
            rpc_id (int): the 16-bit id of the RPC we want to call
            payload (bytearray): the payload of the command
            timeout (float): the number of seconds to wait for the RPC to execute
            callback (callable): A callback for when we have finished the RPC.  The callback will be called as"
                callback(connection_id, adapter_id, success, failure_reason, status, payload)
                'connection_id': the connection id
                'adapter_id': this adapter's id
                'success': a bool indicating whether we received a response to our attempted RPC
                'failure_reason': a string with the reason for the failure if success == False
                'status': the one byte status code returned for the RPC if success == True else None
                'payload': a bytearray with the payload returned by RPC if success == True else None
        """

        try:
            self.connections.get_connection_id(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information", None, None)
            return

        self.connections.begin_operation(connection_id, 'rpc', callback, timeout)

        try:
            result = self.client.send_command('send_rpc', {
                'address': address,
                'rpc_id': rpc_id,
                'payload': payload,
                'timeout': timeout
            })
        except Exception as err:
            reason = "Error while sending command 'send_rpc' to ws server: {}".format(err)
            self.connections.finish_operation(connection_id, False, reason, None, None)
            raise HardwareError(reason)

        payload = result.get('payload')
        status = 0xFF
        return_value = bytearray()

        if payload is not None:
            status = payload.get('status', status)
            return_value = payload.get('return_value', return_value)

        # FIXME: async after creating WebSocketHandler2
        self.connections.finish_operation(
            connection_id,
            result['success'],
            result.get('reason', None),
            status,
            return_value
        )

    def send_script_async(self, connection_id, data, progress_callback, callback):
        """Asynchronously send a a script to this IOTile device

        Args:
            connection_id (int): A unique identifier that will refer to this connection
            data (string): the script to send to the device
            progress_callback (callable): A function to be called with status on our progress, called as:
                progress_callback(done_count, total_count)
            callback (callable): A callback for when we have finished sending the script. The callback will be called as
                callback(connection_id, adapter_id, success, failure_reason)
                'connection_id': the connection id
                'adapter_id': this adapter's id
                'success': a bool indicating whether we received a response to our attempted RPC
                'failure_reason': a string with the reason for the failure if success == False
        """

        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        context['progress_callback'] = progress_callback

        self.connections.begin_operation(connection_id, 'script', callback, self.get_config('default_timeout'))

        nb_chunks = 1
        if len(data) > self.mtu:
            nb_chunks = len(data) // self.mtu
            if len(data) % self.mtu != 0:
                nb_chunks += 1

        # Send the script out possibly in multiple chunks if it's larger than our maximum transmit unit
        for i in range(0, nb_chunks):
            start = i * self.mtu
            chunk = data[start:start + self.mtu]

            try:
                result = self.client.send_command('send_script', {
                    'script': chunk,
                    'connection_id': connection_id,
                    'fragment_count': nb_chunks,
                    'fragment_index': i
                })
                if not result['success']:
                    raise Exception(result['reason'])
            except Exception as err:
                reason = "Error while sending command 'send_rpc' to ws server: {}".format(err)
                self.connections.finish_operation(connection_id, False, reason)
                raise HardwareError(reason)

        if 'progress_callback' in context:
            del context['progress_callback']

        self.connections.finish_operation(
            connection_id,
            result.get('success', False),
            result.get('failure_reason', None)
        )

    def _open_rpc_interface(self, connection_id, callback):
        """Enable RPC interface for this IOTile device

        Args:
            connection_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(connection_id, adapter_id, success, failure_reason)
        """

        self._open_interface(connection_id, 'rpc', callback)

    def _open_streaming_interface(self, connection_id, callback):
        """Enable streaming interface for this IOTile device

        Args:
            connection_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(connection_id, adapter_id, success, failure_reason)
        """

        self._open_interface(connection_id, 'streaming', callback)

    def _open_tracing_interface(self, connection_id, callback):
        """Enable tracing interface for this IOTile device

        Args:
            connection_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(connection_id, adapter_id, success, failure_reason)
        """

        self._open_interface(connection_id, 'tracing', callback)

    def _open_script_interface(self, connection_id, callback):
        """Enable script interface for this IOTile device

        Args:
            connection_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(connection_id, adapter_id, success, failure_reason)
        """

        self._open_interface(connection_id, 'script', callback)

    def _open_interface(self, connection_id, interface, callback):
        """Open an interface on this device

        Args:
            connection_id (int): the unique identifier for the connection
            interface (string): the interface name to open
            callback (callback): Callback to be called when this command finishes
                callback(connection_id, adapter_id, success, failure_reason)
        """

        try:
            self.connections.get_connection_id(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        self.connections.begin_operation(connection_id, 'open_interface', callback, self.get_config('default_timeout'))

        try:
            result = self.client.send_command('open_interface', {'interface': interface})
        except Exception as err:
            reason = "Error while sending command 'open_interface' to ws server: {}".format(err)
            self.connections.finish_connection(connection_id, False, reason)
            raise HardwareError(reason)

        # FIXME: async after creating WebSocketHandler2
        self.connections.finish_operation(connection_id, result['success'], result.get('reason', None))

    def on_trace_chunk_received(self, trace_chunk):
        # TODO: replace None by connection_id, received from 'server'
        self._trigger_callback('on_trace', None, bytearray(trace_chunk['payload']))

    def on_report_chunk_received(self, report_chunk):
        self.parser.add_data(bytearray(report_chunk['payload']))

    def _on_report(self, report, connection_id):
        self.logger.info('Received report: {}'.format(str(report)))
        self._trigger_callback('on_report', connection_id, report)

        return False

    def _on_report_error(self, code, message, connection_id):
        self.logger.error("Report Error, code={}, message={}".format(code, message))

    def on_progress_script(self, notification):
        try:
            context = self.connections.get_context(notification['connection_id'])
        except ArgumentError:
            self.logger.warn(
                "Dropping message that does not correspond with a known connection, message={}"
                .format(notification)
            )
            return

        progress_callback = context.get('progress_callback', None)
        if progress_callback is not None:
            progress_callback(notification['done_count'], notification['total_count'])

    def periodic_callback(self):
        """Periodic cleanup tasks to maintain this adapter."""

        pass
