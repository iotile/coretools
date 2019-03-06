# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import base64
import logging
from time import monotonic
import threading
from iotile.core.hw.transport.adapter import DeviceAdapter
from iotile.core.utilities.validating_wsclient import ValidatingWSClient
from iotile.core.hw.reports.parser import IOTileReportParser
from iotile.core.exceptions import ArgumentError, HardwareError
from .connection_manager import ConnectionManager
from .protocol import notifications, operations, responses


class WebSocketDeviceAdapter(DeviceAdapter):
    """ A device adapter allowing connections to devices over WebSockets

    Args:
        port (string): A url for the WebSocket server in form of server:port
        autoprobe_interval (int): If not None, run a probe refresh every `autoprobe_interval` seconds
    """

    def __init__(self, port, autoprobe_interval=None):
        super(WebSocketDeviceAdapter, self).__init__()

        # Configuration
        self.set_config('default_timeout', 10.0)
        self.set_config('expiration_time', 60.0)
        self.set_config('maximum_connections', 100)
        self.set_config('probe_required', True)
        self.set_config('probe_supported', True)

        # Set logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)  # TODO: remove this line
        self.logger.addHandler(logging.NullHandler())

        # WebSocket client
        path = "ws://{0}/iotile/v2".format(port)
        self.client = ValidatingWSClient(path)

        self.client.add_message_type(responses.Connect, self._on_connection_finished)
        self.client.add_message_type(responses.Disconnect, self._on_disconnection_finished)
        self.client.add_message_type(responses.Scan, self._on_probe_finished)
        self.client.add_message_type(responses.SendRPC, self._on_rpc_finished)
        self.client.add_message_type(responses.SendScript, self._on_script_finished)
        self.client.add_message_type(responses.OpenInterface, self._on_interface_opened)
        self.client.add_message_type(responses.CloseInterface, self._on_interface_closed)
        self.client.add_message_type(responses.Unknown, self._on_unknown_response)
        self.client.add_message_type(notifications.DeviceFound, self._on_device_found)
        self.client.add_message_type(notifications.Report, self._on_report_chunk_received)
        self.client.add_message_type(notifications.Trace, self._on_trace_chunk_received)
        self.client.add_message_type(notifications.Progress, self._on_progress_notification)
        self.client.disconnection_callback = self._on_websocket_disconnect

        self.client.start()

        # To manage multiple connections
        self.connections = ConnectionManager(self.id)
        self.connections.start()

        # Probe variables
        self.probe_callbacks = []
        self.probe_callbacks_lock = threading.Lock()
        self.last_probe = 0
        self.autoprobe_interval = float(autoprobe_interval) if autoprobe_interval is not None else None

    def can_connect(self):
        """Check if this adapter can take another connection

        Returns:
            bool: whether there is room for one more connection
        """

        connections = self.connections.get_connections()
        return len(connections) < int(self.get_config('maximum_connections'))

    def connect_async(self, connection_id, connection_string, callback):
        """Asynchronously connect to a device by its connection_string

        Args:
            connection_id (int): A unique integer set by the caller for referring to this connection
                once created
            connection_string (string): A DeviceAdapter specific string that can be used to connect to
                a device using this DeviceAdapter.
            callback (callable): A callback function called when the connection has succeeded or
                failed
        """

        context = {
            'connection_string': connection_string
        }
        self.connections.begin_connection(
            connection_id,
            connection_string,
            callback,
            context,
            self.get_config('default_timeout')
        )

        try:
            self.send_command_async(operations.CONNECT, connection_string=connection_string)
        except Exception as err:
            failure_reason = "Error while sending 'connect' command to ws server: {}".format(err)
            self.connections.finish_connection(connection_id, False, failure_reason)
            raise HardwareError(failure_reason)

    def _on_connection_finished(self, response):
        """Callback function called when a connection has finished.

        Args:
            response (dict): The response data
        """

        self.connections.finish_connection(
            response['connection_string'],
            response['success'],
            response.get('failure_reason', None)
        )

    def disconnect_async(self, connection_id, callback):
        """Asynchronously disconnect from a device that has previously been connected

        Args:
            connection_id (int): a unique identifier for this connection on the DeviceManager
                that owns this adapter.
            callback (callable): A function called as callback(connection_id, adapter_id, success, failure_reason)
            when the disconnection finishes.  Disconnection can only either succeed or timeout.
        """

        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        connection_string = context['connection_string']

        self.connections.begin_disconnection(connection_id, callback, self.get_config('default_timeout'))

        try:
            self.send_command_async(operations.DISCONNECT, connection_string=connection_string)
        except Exception as err:
            failure_reason = "Error while sending 'disconnect' command to ws server: {}".format(err)
            self.connections.finish_disconnection(connection_id, False, failure_reason)
            raise HardwareError(failure_reason)

    def _on_disconnection_finished(self, response):
        """Callback function called when a disconnection has finished.

        Args:
            response (dict): The response data
        """

        self.connections.finish_disconnection(
            response['connection_string'],
            response['success'],
            response.get('failure_reason', None)
        )

    def probe_async(self, callback):
        """Asynchronously probe for visible devices connected to this DeviceAdapter.

        Args:
            callback (callable): A callback for when the probe operation has completed.
                callback should have signature callback(adapter_id, success, failure_reason) where:
                    success: bool
                    failure_reason: None if success is True, otherwise a reason for why we could not probe
        """

        self._add_probe_callback(callback)
        self.last_probe = monotonic()

        try:
            self.send_command_async(operations.SCAN)
        except Exception as err:
            raise HardwareError("Error while sending 'probe' command to ws server: {}".format(err))

    def _on_device_found(self, response):
        """Callback function called when a new device has been scanned by the probe.

        Args:
            response (dict): The response data
        """

        self._trigger_callback('on_scan', self.id, response['device'], self.get_config('expiration_time'))

    def _on_probe_finished(self, response):
        """Callback function called when a probe has finished.

        Args:
            response (dict): The response data
        """

        self._consume_probe_callbacks(response['success'], response.get('failure_reason', None))

        # As probe is not handled by the connection manager (because there is no connection_id/connection_string),
        # we have to throw errors manually
        if not response['success']:
            raise HardwareError(response['failure_reason'])

    def send_rpc_async(self, connection_id, address, rpc_id, payload, timeout, callback):
        """Asynchronously send an RPC to this IOTile device

        Args:
            connection_id (int): A unique identifier that will refer to this connection
            address (int): the address of the tile that we wish to send the RPC to
            rpc_id (int): the 16-bit id of the RPC we want to call
            payload (bytes): the payload of the command
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
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information", None, None)
            return

        connection_string = context['connection_string']

        self.connections.begin_operation(connection_id, 'rpc', callback, timeout)

        try:
            self.send_command_async(operations.SEND_RPC,
                                    connection_string=connection_string,
                                    address=address,
                                    rpc_id=rpc_id,
                                    payload=base64.b64encode(payload),
                                    timeout=timeout)
        except Exception as err:
            failure_reason = "Error while sending 'send_rpc' command to ws server: {}".format(err)
            self.connections.finish_operation(connection_id, False, failure_reason, None, None)
            raise HardwareError(failure_reason)

    def _on_rpc_finished(self, response):
        """Callback function called when an RPC command has finished.

        Args:
            response (dict): The response data (eventually contains data returned by the RPC)
        """

        self.connections.finish_operation(
            response['connection_string'],
            response['success'],
            response.get('failure_reason', None),
            response['status'],
            base64.b64decode(response['return_value'])
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

        connection_string = context['connection_string']
        context['progress_callback'] = progress_callback

        self.connections.begin_operation(connection_id, 'script', callback, self.get_config('default_timeout'))

        mtu = int(self.get_config('mtu', 60*1024))  # Split script payloads larger than this

        # Count number of chunks to send
        nb_chunks = 1
        if len(data) > mtu:
            nb_chunks = len(data) // mtu
            if len(data) % mtu != 0:
                nb_chunks += 1

        # Send the script out possibly in multiple chunks if it's larger than our maximum transmit unit
        for i in range(0, nb_chunks):
            start = i * mtu
            chunk = data[start:start + mtu]

            try:
                self.send_command_async(operations.SEND_SCRIPT,
                                        connection_string=connection_string,
                                        script=base64.b64encode(chunk),
                                        fragment_count=nb_chunks,
                                        fragment_index=i)
            except Exception as err:
                failure_reason = "Error while sending 'send_script' command to ws server: {}".format(err)
                self.connections.finish_operation(connection_id, False, failure_reason)
                raise HardwareError(failure_reason)

    def _on_script_finished(self, response):
        """Callback function called when a script has been fully sent to a device.

        Args:
            response (dict): The response
        """

        self.connections.finish_operation(
            response['connection_string'],
            response.get('success', False),
            response.get('failure_reason', None)
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
        """Enable streaming interface for this IOTile device (to receive reports).

        Args:
            connection_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(connection_id, adapter_id, success, failure_reason)
        """

        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        # Create a parser to parse reports
        context['parser'] = IOTileReportParser(report_callback=self._on_report, error_callback=self._on_report_error)
        context['parser'].context = connection_id

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

    def _open_debug_interface(self, connection_id, callback, connection_string=None):
        """Enable debug interface for this IOTile device

        Args:
            connection_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(connection_id, adapter_id, success, failure_reason)
        """

        self._open_interface(connection_id, 'debug', callback)

    def _open_interface(self, connection_id, interface, callback):
        """Asynchronously open an interface on the device

        Args:
            connection_id (int): the unique identifier for the connection
            interface (string): the interface name to open
            callback (callback): Callback to be called when this command finishes
                callback(connection_id, adapter_id, success, failure_reason)
        """

        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        connection_string = context['connection_string']

        self.connections.begin_operation(connection_id, 'open_interface', callback, self.get_config('default_timeout'))

        try:
            self.send_command_async(
                operations.OPEN_INTERFACE,
                connection_string=connection_string,
                interface=interface
            )
        except Exception as err:
            failure_reason = "Error while sending 'open_interface' command to ws server: {}".format(err)
            self.connections.finish_operation(connection_id, False, failure_reason)
            raise HardwareError(failure_reason)

    def _on_interface_opened(self, response):
        """Callback function called when an interface has been opened.

        Args:
            response (dict): The response data
        """

        self.connections.finish_operation(
            response['connection_string'],
            response['success'],
            response.get('failure_reason', None)
        )

    def _close_rpc_interface(self, connection_id, callback):
        """Disable RPC interface for this IOTile device

        Args:
            connection_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(connection_id, adapter_id, success, failure_reason)
        """

        self._close_interface(connection_id, 'rpc', callback)

    def _close_streaming_interface(self, connection_id, callback):
        """Disable streaming interface for this IOTile device

        Args:
            connection_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(connection_id, adapter_id, success, failure_reason)
        """

        self._close_interface(connection_id, 'streaming', callback)

    def _close_tracing_interface(self, connection_id, callback):
        """Disable tracing interface for this IOTile device

        Args:
            connection_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(connection_id, adapter_id, success, failure_reason)
        """

        self._close_interface(connection_id, 'tracing', callback)

    def _close_script_interface(self, connection_id, callback):
        """Disable script interface for this IOTile device

        Args:
            connection_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(connection_id, adapter_id, success, failure_reason)
        """

        self._close_interface(connection_id, 'script', callback)

    def _close_debug_interface(self, connection_id, callback):
        """Disable debug interface for this IOTile device

        Args:
            connection_id (int): the unique identifier for the connection
            callback (callback): Callback to be called when this command finishes
                callback(connection_id, adapter_id, success, failure_reason)
        """

        self._close_interface(connection_id, 'debug', callback)

    def _close_interface(self, connection_id, interface, callback):
        """Asynchronously close an interface on the device

        Args:
            connection_id (int): the unique identifier for the connection
            interface (string): the interface name to open
            callback (callback): Callback to be called when this command finishes
                callback(connection_id, adapter_id, success, failure_reason)
        """

        try:
            context = self.connections.get_context(connection_id)
        except ArgumentError:
            callback(connection_id, self.id, False, "Could not find connection information")
            return

        connection_string = context['connection_string']

        self.connections.begin_operation(connection_id, 'close_interface', callback, self.get_config('default_timeout'))

        try:
            self.send_command_async(
                operations.CLOSE_INTERFACE,
                connection_string=connection_string,
                interface=interface
            )
        except Exception as err:
            failure_reason = "Error while sending 'close_interface' command to ws server: {}".format(err)
            self.connections.finish_operation(connection_id, False, failure_reason)
            raise HardwareError(failure_reason)

    def _on_interface_closed(self, response):
        """Callback function called when an interface has been closed.

        Args:
            response (dict): The response data
        """

        self.connections.finish_operation(
            response['connection_string'],
            response['success'],
            response.get('failure_reason', None)
        )

    def _on_report_chunk_received(self, report_chunk):
        """Callback function called when a report chunk is received.

        Args:
            report_chunk (dict): The received report chunk information
        """

        try:
            context = self.connections.get_context(report_chunk['connection_string'])
        except ArgumentError:
            self.logger.warn(
                "Dropping report message that does not correspond with a known connection, connection_string={}"
                .format(report_chunk['connection_string'])
            )
            return

        if 'parser' not in context:
            self.logger.warn(
                "No parser found for given connection, connection_string={}"
                .format(report_chunk['connection_string'])
            )
            return

        decoded_payload = base64.b64decode(report_chunk['payload'])
        context['parser'].add_data(decoded_payload)

    def _on_report(self, report, context):
        """Callback function called when a report has been fully received and parsed.

        Args:
            report (IOTileReport): The report instance
            context (any): The context passed to the report parser (here is probably the connection_id)

        Returns:
            False to delete the report from internal storage
        """

        self.logger.info('Received report: {}'.format(str(report)))
        self._trigger_callback('on_report', context, report)

        return False

    def _on_report_error(self, code, message, context):
        """Callback function called when an error occurred while parsing a report.

        Args:
            code (int): Error code
            message (str): The failure failure_reason
            context (any): The context passed to the report parser (here is probably the connection_id)
        """

        self.logger.error("Report Error, code={}, message={}".format(code, message))

    def _on_trace_chunk_received(self, trace_chunk):
        """Callback function called when a trace chunk is received.

        Args:
            trace_chunk (dict): The received trace chunk information
        """

        try:
            connection_id = self.connections.get_connection_id(trace_chunk['connection_string'])
        except ArgumentError:
            self.logger.warn(
                "Dropping trace message that does not correspond with a known connection, connection_string={}"
                .format(trace_chunk['connection_string'])
            )
            return

        decoded_payload = base64.b64decode(trace_chunk['payload'])
        self._trigger_callback('on_trace', connection_id, decoded_payload)

    def _on_progress_notification(self, notification):
        """Callback function called when a progress notification is received.

        Args:
            notification (dict): The received notification containing the progress information
        """

        try:
            context = self.connections.get_context(notification['connection_string'])
        except ArgumentError:
            self.logger.warn(
                "Dropping progress message that does not correspond with a known connection, message={}"
                .format(notification)
            )
            return

        progress_callback = context.get('progress_callback', None)

        if progress_callback is not None:
            done_count = notification['done_count']
            total_count = notification['total_count']

            progress_callback(done_count, total_count)

            if done_count >= notification['total_count']:
                # Remove the progress callback as it is not needed anymore
                del context['progress_callback']

    def send_command_async(self, operation, **kwargs):
        """Send a command and do not wait for the response (which should be handled by a callback function).

        Args:
            operation (string): The operation name
            **kwargs: Optional arguments
        """

        message = dict({
            'type': 'command',
            'operation': operation
        }, **kwargs)

        self.client.send_message(message)

    def _on_websocket_disconnect(self):
        """Callback function called when we have been disconnected from the server (by error or not).
        Allows to clean all if the disconnection was unexpected."""

        self.logger.info('Disconnected from the WebSocket server')

        self._consume_probe_callbacks(True, None)

        for connection_id in self.connections.get_connections():
            self.connections.unexpected_disconnect(connection_id)
            self._trigger_callback('on_disconnect', self.id, connection_id)

    def _on_unknown_response(self, response):
        """Callback function called when we receive a response with an '<unknown>' operation. This could happen
        for example if an error independent of the operation occurred.

        Args:
            response (dict): The response data
        """

        if response['success']:
            self.logger.info('Message with unknown operation received: {}'.format(response))

        else:
            self.logger.error('Error with unknown operation received: {}'.format(response))

    def stop_sync(self):
        """Synchronously stop this adapter."""

        for connection_id in list(self.connections.get_connections()):
            try:
                self.disconnect_sync(connection_id)
            except HardwareError:
                pass

        self.client.stop()
        self.connections.stop()

    def periodic_callback(self):
        """Periodically help maintain adapter internal state."""

        now = monotonic()

        if len(self.probe_callbacks) > 0:
            # Currently probing: check if not timed out
            if (now - self.last_probe) > self.get_config('default_timeout'):
                self._consume_probe_callbacks(False, 'Timeout while waiting for scan response')

        elif self.autoprobe_interval is not None:
            # Probe every `autoprobe_interval` seconds to keep up to date scan results
            if self.client.connected and (now - self.last_probe) > self.autoprobe_interval:
                self.logger.info('Refreshing probe results...')
                self.probe_async(lambda adapter_id, success, failure_reason: None)

    def _add_probe_callback(self, callback):
        with self.probe_callbacks_lock:
            self.probe_callbacks += [callback]

    def _consume_probe_callbacks(self, success, reason):
        with self.probe_callbacks_lock:
            for probe_callback in self.probe_callbacks:
                probe_callback(self.id, success, reason)
            del self.probe_callbacks[:]
