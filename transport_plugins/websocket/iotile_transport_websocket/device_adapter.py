# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import base64
import logging
import asyncio
from iotile.core.hw.transport.adapter import StandardDeviceAdapter
from iotile.core.utilities.schema_verify import NoneVerifier

from iotile.core.hw.reports.parser import IOTileReportParser
from iotile.core.hw.exceptions import DeviceAdapterError
from iotile.core.exceptions import ArgumentError, HardwareError, ExternalError
from .protocol import OPERATIONS, NOTIFICATIONS, COMMANDS
from .generic import AsyncValidatingWSClient


class WebSocketDeviceAdapter(StandardDeviceAdapter):
    """ A device adapter allowing connections to devices over WebSockets

    Args:
        port (string): A url for the WebSocket server in form of server:port
    """

    def __init__(self, port):
        super(WebSocketDeviceAdapter, self).__init__()

        # Configuration
        self.set_config('default_timeout', 10.0)
        self.set_config('expiration_time', 60.0)
        self.set_config('max_connections', 100)
        self.set_config('probe_required', True)
        self.set_config('probe_supported', True)

        # Set logger
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())

        # WebSocket client
        path = "ws://{0}/iotile/v2".format(port)
        self.client = AsyncValidatingWSClient(path)

        self.client.register_event(OPERATIONS.NOTIFY_DEVICE_FOUND, self._on_device_found,
                                   NOTIFICATIONS.ScanEvent)
        self.client.register_event(AsyncValidatingWSClient.DISCONNECT_EVENT,
                                   self._on_websocket_disconnect, NoneVerifier())

    async def start(self):
        await self.client.start()

    async def stop(self):
        await self.client.stop()

    async def probe(self):
        await self._send_command(OPERATIONS.PROBE, None, COMMANDS.ProbeResponse)

    async def connect(self, conn_id, connection_string):
        self._ensure_connection(conn_id, False)

        msg = dict(connection_string=connection_string)
        await self._send_command(OPERATIONS.CONNECT, msg, COMMANDS.ConnectResponse)

        self._setup_connection(conn_id, connection_string)

    async def disconnect(self, conn_id):
        self._ensure_connection(conn_id, True)

        msg = dict(connection_string=self._get_property(conn_id, "connection_string"))

        try:
            await self._send_command(OPERATIONS.DISCONNECT, msg, COMMANDS.DisconnectResponse)
        finally:
            self._teardown_connection(conn_id)

    async def open_interface(self, conn_id, interface):
        self._ensure_connection(conn_id, True)
        connection_string = self._get_property(conn_id, "connection_string")

        msg = dict(interface=interface, connection_string=connection_string)
        await self._send_command(OPERATIONS.OPEN_INTERFACE, msg, COMMANDS.OpenInterfaceResponse)

    async def close_interface(self, conn_id, interface):
        self._ensure_connection(conn_id, True)
        connection_string = self._get_property(conn_id, "connection_string")

        msg = dict(interface=interface, connection_string=connection_string)
        await self._send_command(OPERATIONS.CLOSE_INTERFACE, msg, COMMANDS.CloseInterfaceResponse)

    async def send_rpc(self, conn_id, address, rpc_id, payload, timeout):
        self._ensure_connection(conn_id, True)
        connection_string = self._get_property(conn_id, "connection_string")

        msg = dict(address=address, rpc_id=rpc_id, payload=payload, timeout=timeout,
                   connection_string=connection_string)

        response = await self._send_command(OPERATIONS.SEND_RPC, msg, COMMANDS.SendRPCResponse,
                                            timeout=timeout)

        return response.get('status'), response.get('payload')

    def _on_device_found(self, device):
        """Callback function called when a new device has been scanned by the probe.

        Args:
            response (dict): The device advertisement data
        """

        expiration_time = device.get('validity_period', self.get_config('expiration_time'))
        self.fire_event(device.get('connection_string'), 'device_seen', device)

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

    def _on_websocket_disconnect(self, _event):
        """Callback function called when we have been disconnected from the server (by error or not).
        Allows to clean all if the disconnection was unexpected."""

        self.logger.info('Forcibly disconnected from the WebSocket server')

        conns = self._connections.copy()
        for conn_id in conns:
            conn_string = self._get_property(conn_id, 'connection_string')
            self._teardown_connection(conn_id)
            self.notify_event_nowait(conn_string, 'disconnect', "Websocket connection closed")

    async def _send_command(self, name, args, verifier, timeout=10.0):
        try:
            return await self.client.send_command(name, args, verifier, timeout=timeout)
        except ExternalError as err:
            raise DeviceAdapterError(None, name, err.params['reason'])
        except asyncio.TimeoutError as err:
            raise DeviceAdapterError(None, name, 'operation timed out after %f seconds' % timeout)
