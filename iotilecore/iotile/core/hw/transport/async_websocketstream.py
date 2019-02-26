from __future__ import unicode_literals

import threading
from queue import Queue, Empty
import datetime
import time
import msgpack
import base64

from ws4py.client.threadedclient import WebSocketClient
import websockets

from iotile.core.hw.exceptions import *
from iotile.core.exceptions import *
from iotile.core.hw.reports import IOTileReportParser, BroadcastReport, IOTileReading
from .cmdstream import CMDStream

from iotile.core.utilities.event_loop import EventLoop
import asyncio


class AsyncWSIOTileClient:
    def __init__(self, port, report_callback):
        #super(WSIOTileClient, self).__init__(port, protocols=['iotile-ws', 'iotile-ws-text'])

        self.loop = EventLoop().get_loop()

        self.messages = asyncio.Queue()
        self.binary = True
        self.report_callback = report_callback
        self.report_parser = IOTileReportParser()

        self.port = port

        self.con = None

        self.start()

    def start(self):
        """Create the connection"""
        print("creating the connection")
        if not self.con:
            asyncio.ensure_future(self.connection_object(), loop=self.loop)
            asyncio.ensure_future(self.handle_message(), loop=self.loop)

    async def connection_object(self):
        print("creating connection")
        self.con = await websockets.connect(self.port)

    async def close(self):
        if self.con:
            await self.con.close()

    def unpack(self, msg):
        if self.binary is False:
            msg = base64.standard_b64decode(msg)

        return msgpack.unpackb(msg, raw=False, object_hook=self.decode_datetime)

    @classmethod
    def decode_datetime(cls, obj):
        if '__datetime__' in obj:
            obj = datetime.datetime.strptime(obj['as_str'].decode(), "%Y%m%dT%H:%M:%S.%fZ")
        return obj

    @classmethod
    def encode_datetime(cls, obj):
        if isinstance(obj, datetime.datetime):
            obj = {'__datetime__': True, 'as_str': obj.strftime("%Y%m%dT%H:%M:%S.%fZ").encode()}
        return obj

    async def handle_message(self):
        """Loop for handling all incoming messages on the websocket client"""
        while not self.con:
            await asyncio.sleep(1)
        try:
            while True:
                message = await self.con.recv()
                asyncio.ensure_future(self.process_message(message), loop=self.loop)
        finally:
            await self.con.close()

    async def process_message(self, message):
        unpacked_message = self.unpack(message)

        if 'type' in unpacked_message and unpacked_message['type'] == 'report':
            report = self.report_parser.deserialize_report(unpacked_message['value'])
            self.report_callback(report)
        else:
            self.messages.put(unpacked_message)


class AsyncWebSocketStream(CMDStream):
    """An IOTile commander transport stream using web sockets to a server.

    The server is responsible for implementing direct communication with the IOTile devices.
    This stream just provides a generic way to connect to a websockets based server.

    If connection_string is not None, a connection will be made immediately to a specific IOTile
    device.  Otherwise, no connection will be made and devices can be discovered by using the
    scan routine.

    Args:
        port (str): A url for the websocket server in form of server:port/path
        connection_string (str): a protocol specific connection string indicating a specific device
    """

    def __init__(self, port, connection_string, record=None):
        port = "ws://{0}".format(port)
        self._report_queue = Queue()
        self._broadcast_queue = None

        self.loop = EventLoop.get_loop()

        # Make sure we make at least one call here in main thread to workaround python bug
        # https://bugs.python.org/issue7980
        _throwaway = datetime.datetime.strptime('20110101', '%Y%m%d')

        print("sneaky websocket stream threaded")

        self.client = AsyncWSIOTileClient(port, report_callback=self._report_callback)
        self.client.start()
        print("cleint starting")

        self.command_lock = asyncio.Lock()

        self._connection_id = None

        CMDStream.__init__(self, port, connection_string, record=record)

    async def _close(self):
        if self.client.con:
            await self.client.close()

    async def _scan(self, wait=None):

        result = await self.send('scan')

        return result['devices']

    async def _connect(self, uuid_value, wait=None):
        args = {}
        args['uuid'] = uuid_value

        result = await self.send('connect', args)
        self._connection_id = result['connection_id']

        connstring = result['connection_string']

        try:
            result = await self.send('open_interface', {'interface': 'rpc'})
        except:
            self._disconnect()
            raise

        return connstring

    async def _connect_direct(self, connection_string):
        args = {}
        args['connection_string'] = connection_string

        result = await self.send('connect_direct', args)
        self._connection_id = result['connection_id']

        try:
            result = await self.send('open_interface', {'interface': 'rpc'})
        except:
            self._disconnect()
            raise

    async def _enable_streaming(self):
        await self.send('open_interface', {'interface': 'streaming'})
        return self._report_queue

    def _enable_broadcasting(self):
        self._broadcast_queue = Queue()
        return self._broadcast_queue

    async def _send_rpc(self, address, rpc_id, payload, **kwargs):
        args = {}
        args['rpc_address'] = address
        args['rpc_feature'] = rpc_id >> 8
        args['rpc_command'] = rpc_id & 0xFF
        args['rpc_payload'] = bytes(payload)

        timeout = 3.0
        if 'timeout' in kwargs:
            timeout = float(kwargs['timeout'])

        args['rpc_timeout'] = timeout

        result = await self.send('send_rpc', args)
        status = result['status']
        payload = result['payload']

        return status, payload

    async def _disconnect(self):
        await self.send('disconnect')

    def _report_callback(self, report):
        if isinstance(report, BroadcastReport):
            if self._broadcast_queue is None:
                return

            self._broadcast_queue.put(report)
        else:
            self._report_queue.put(report)

    async def send(self, command, args=None, progress=None, timeout=10.0):
        cmd = {}
        cmd['command'] = command

        if args is None:
            args = {}

        cmd.update(args)

        msg = msgpack.packb(cmd, use_bin_type=True)

        while not self.client.con:
            asyncio.sleep(0.5)

        print("sending comand ")

        async with self.command_lock:
            await self.client.con.send(msg)
            done = False
            while not done:
                try:
                    result = await asyncio.wait_for(self.client.messages.get(), timeout=timeout, loop=EventLoop.get_loop())
                except asyncio.TimeoutError:
                    raise TimeoutExpiredError("Timeout waiting for respnose to %s command from websocket server" % command)
                if 'type' in result and result['type'] == 'progress':
                    total = result['total']
                    current = result['current']

                    if progress:
                        progress(current, total)
                else:
                    done = True

            if result['success'] != True:
                raise HardwareError("Error processing command", reason=result['reason'])

            return result


    def _send_highspeed(self, data, progress_callback):
        self.send('send_script', {'data': str(data)}, progress=progress_callback)
