# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import base64
import logging
import asyncio
from iotile.core.hw.transport.adapter import StandardDeviceAdapter
from iotile.core.utilities.schema_verify import NoneVerifier
from iotile.core.utilities import SharedLoop
from iotile.core.hw.virtual import unpack_rpc_response
from iotile.core.hw.reports import IOTileReportParser
from iotile.core.hw.exceptions import DeviceAdapterError
from iotile.core.exceptions import ExternalError
from .protocol import OPERATIONS, NOTIFICATIONS, COMMANDS
from .generic import AsyncValidatingWSClient


class WebSocketDeviceAdapter(StandardDeviceAdapter):
    """ A device adapter allowing connections to devices over WebSockets.

    Args:
        port (string): A target for the WebSocket client to connect to in form of
            server:port.  For example, "localhost:5120".
        loop (BackgroundEventLoop): Loop for running our websocket client.
    """

    def __init__(self, port, *, loop=SharedLoop):
        super(WebSocketDeviceAdapter, self).__init__(loop=loop)

        # Configuration
        self.set_config('default_timeout', 10.0)
        self.set_config('expiration_time', 60.0)
        self.set_config('max_connections', 100)
        self.set_config('probe_required', True)
        self.set_config('probe_supported', True)

        # Set logger
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())

        self._report_parser = IOTileReportParser()

        # WebSocket client
        path = "ws://{0}/iotile/v3".format(port)
        self.client = AsyncValidatingWSClient(path, loop=loop)

        self.client.register_event(OPERATIONS.NOTIFY_DEVICE_FOUND, self._on_device_found,
                                   NOTIFICATIONS.ScanEvent)
        self.client.register_event(OPERATIONS.NOTIFY_TRACE, self._on_trace_notification,
                                   NOTIFICATIONS.TraceEvent)
        self.client.register_event(OPERATIONS.NOTIFY_REPORT, self._on_report_notification,
                                   NOTIFICATIONS.ReportEvent)
        self.client.register_event(OPERATIONS.NOTIFY_BROADCAST, self._on_broadcast_notification,
                                   NOTIFICATIONS.ReportEvent)
        self.client.register_event(OPERATIONS.NOTIFY_PROGRESS, self._on_progress_notification,
                                   NOTIFICATIONS.ProgressEvent)
        self.client.register_event(AsyncValidatingWSClient.DISCONNECT_EVENT,
                                   self._on_websocket_disconnect, NoneVerifier())

    async def start(self):
        """Start the device adapter.

        See :meth:`AbstractDeviceAdapter.start`.
        """

        await self.client.start()

    async def stop(self):
        """Stop the device adapter.

        See :meth:`AbstractDeviceAdapter.stop`.
        """

        await self.client.stop()

    async def probe(self):
        """Probe for devices connected to this adapter.

        See :meth:`AbstractDeviceAdapter.probe`.
        """

        await self._send_command(OPERATIONS.PROBE, None, COMMANDS.ProbeResponse)

    async def connect(self, conn_id, connection_string):
        """Connect to a device.

        See :meth:`AbstractDeviceAdapter.connect`.
        """

        self._ensure_connection(conn_id, False)

        msg = dict(connection_string=connection_string)
        await self._send_command(OPERATIONS.CONNECT, msg, COMMANDS.ConnectResponse)

        self._setup_connection(conn_id, connection_string)

    async def disconnect(self, conn_id):
        """Disconnect from a connected device.

        See :meth:`AbstractDeviceAdapter.disconnect`.
        """

        self._ensure_connection(conn_id, True)

        msg = dict(connection_string=self._get_property(conn_id, "connection_string"))

        try:
            await self._send_command(OPERATIONS.DISCONNECT, msg, COMMANDS.DisconnectResponse)
        finally:
            self._teardown_connection(conn_id)

    async def open_interface(self, conn_id, interface):
        """Open an interface on an IOTile device.

        See :meth:`AbstractDeviceAdapter.open_interface`.
        """

        self._ensure_connection(conn_id, True)
        connection_string = self._get_property(conn_id, "connection_string")

        msg = dict(interface=interface, connection_string=connection_string)
        await self._send_command(OPERATIONS.OPEN_INTERFACE, msg, COMMANDS.OpenInterfaceResponse)

    async def close_interface(self, conn_id, interface):
        """Close an interface on this IOTile device.

        See :meth:`AbstractDeviceAdapter.close_interface`.
        """

        self._ensure_connection(conn_id, True)
        connection_string = self._get_property(conn_id, "connection_string")

        msg = dict(interface=interface, connection_string=connection_string)
        await self._send_command(OPERATIONS.CLOSE_INTERFACE, msg, COMMANDS.CloseInterfaceResponse)

    async def send_rpc(self, conn_id, address, rpc_id, payload, timeout):
        """Send an RPC to a device.

        See :meth:`AbstractDeviceAdapter.send_rpc`.
        """

        self._ensure_connection(conn_id, True)
        connection_string = self._get_property(conn_id, "connection_string")

        msg = dict(address=address, rpc_id=rpc_id, payload=base64.b64encode(payload),
                   timeout=timeout, connection_string=connection_string)

        response = await self._send_command(OPERATIONS.SEND_RPC, msg, COMMANDS.SendRPCResponse,
                                            timeout=timeout)

        return unpack_rpc_response(response.get('status'), response.get('payload'),
                                   rpc_id=rpc_id, address=address)

    async def send_script(self, conn_id, data):
        """Send a a script to this IOTile device

        Args:
            conn_id (int): A unique identifier that will refer to this connection
            data (bytes): the script to send to the device
        """

        self._ensure_connection(conn_id, True)
        connection_string = self._get_property(conn_id, "connection_string")

        msg = dict(connection_string=connection_string, fragment_count=1, fragment_index=0,
                   script=base64.b64encode(data))
        await self._send_command(OPERATIONS.SEND_SCRIPT, msg, COMMANDS.SendScriptResponse)

    async def _on_device_found(self, device):
        """Callback function called when a new device has been scanned by the probe.

        Args:
            response (dict): The device advertisement data
        """

        await self.notify_event(device.get('connection_string'), 'device_seen', device)

    async def _on_report_notification(self, event):
        """Callback function called when a report event is received.

        Args:
            event (dict): The report_event
        """

        conn_string = event.get('connection_string')
        report = self._report_parser.deserialize_report(event.get('serialized_report'))

        self.notify_event(conn_string, 'report', report)

    async def _on_broadcast_notification(self, event):
        """Callback function called when a broadcast event is received.

        Args:
            event (dict): The broadcast event
        """

        conn_string = event.get('connection_string')
        report = self._report_parser.deserialize_report(event.get('serialized_report'))

        self.notify_event(conn_string, 'broadcast', report)

    async def _on_trace_notification(self, trace_event):
        """Callback function called when a trace chunk is received.

        Args:
            trace_chunk (dict): The received trace chunk information
        """

        conn_string = trace_event.get('connection_string')
        payload = trace_event.get('payload')

        await self.notify_event(conn_string, 'trace', payload)

    async def _on_progress_notification(self, progress):
        """Callback function called when a progress notification is received.

        Args:
            progress (dict): The received notification containing the progress information
        """

        conn_string = progress.get('connection_string')
        done = progress.get('done_count')
        total = progress.get('total_count')
        operation = progress.get('operation')

        await self.notify_progress(conn_string, operation, done, total, wait=True)

    async def _on_websocket_disconnect(self, _event):
        """Callback function called when we have been disconnected from the server (by error or not).
        Allows to clean all if the disconnection was unexpected."""

        self.logger.info('Forcibly disconnected from the WebSocket server')

        conns = self._connections.copy()
        for conn_id in conns:
            conn_string = self._get_property(conn_id, 'connection_string')
            self._teardown_connection(conn_id)
            self.notify_event(conn_string, 'disconnect', "Websocket connection closed")

    async def _send_command(self, name, args, verifier, timeout=10.0):
        try:
            return await self.client.send_command(name, args, verifier, timeout=timeout)
        except ExternalError as err:
            raise DeviceAdapterError(None, name, err.params['reason'])
        except asyncio.TimeoutError as err:
            raise DeviceAdapterError(None, name, 'operation timed out after %f seconds' % timeout)
