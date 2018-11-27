from __future__ import unicode_literals

import threading
from queue import Queue, Empty
import datetime
import time
import msgpack
import base64

from ws4py.client.threadedclient import WebSocketClient
from iotile.core.hw.exceptions import *
from iotile.core.exceptions import *
from iotile.core.hw.reports import IOTileReportParser, BroadcastReport, IOTileReading
from .cmdstream import CMDStream


class WSIOTileClient(WebSocketClient):
    def __init__(self, port, report_callback):
        super(WSIOTileClient, self).__init__(port, protocols=['iotile-ws', 'iotile-ws-text'])

        self.connection_established = threading.Event()
        self.messages = Queue()
        self.binary = True
        self.report_callback = report_callback
        self.report_parser = IOTileReportParser()

    def start(self):
        try:
            self.connect()
        except Exception as exc:
           raise HardwareError("Unable to connect to websockets host", reason=str(exc))

        self.connection_established.wait()

    def opened(self):
        protocols = self.protocols

        # Workaround bug in ws4py protocol handling
        if isinstance(protocols, (str, bytes)) and b'i,o,t,i,l,e' in protocols:
            protocols = [protocols.replace(b',', b'')]

        if 'iotile-ws-text' in protocols and 'iotile-ws' not in protocols:
            self.binary = False

        self.connection_established.set()

    def closed(self, code, reason):
        self.connection_established.clear()

    def unpack(self, msg):
        if self.binary is False:
            msg = base64.standard_b64decode(msg)

        return msgpack.unpackb(msg, raw=False, object_hook=self.decode_datetime)

    @classmethod
    def decode_datetime(cls, obj):
        if b'__datetime__' in obj:
            obj = datetime.datetime.strptime(obj[b'as_str'].decode(), "%Y%m%dT%H:%M:%S.%fZ")
        return obj

    @classmethod
    def encode_datetime(cls, obj):
        if isinstance(obj, datetime.datetime):
            obj = {'__datetime__': True, 'as_str': obj.strftime("%Y%m%dT%H:%M:%S.%fZ").encode()}
        return obj

    def received_message(self, message):
        unpacked_message = self.unpack(message.data)

        if 'type' in unpacked_message and unpacked_message['type'] == 'report':
            report = self.report_parser.deserialize_report(unpacked_message['value'])
            self.report_callback(report)
        else:
            self.messages.put(unpacked_message)


class WebSocketStream(CMDStream):
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

        # Make sure we make at least one call here in main thread to workaround python bug
        # https://bugs.python.org/issue7980
        _throwaway = datetime.datetime.strptime('20110101', '%Y%m%d')

        self.client = WSIOTileClient(port, report_callback=self._report_callback)
        self.client.start()
        self.binary = self.client.binary

        self._connection_id = None

        CMDStream.__init__(self, port, connection_string, record=record)

    def _close(self):
        if self.client.connection_established.is_set():
            self.client.close()

    def _scan(self, wait=None):
        result = self.send('scan')
        return result['devices']

    def _connect(self, uuid_value, wait=None):
        args = {}
        args['uuid'] = uuid_value

        result = self.send('connect', args)
        self._connection_id = result['connection_id']

        connstring = result['connection_string']

        try:
            result = self.send('open_interface', {'interface': 'rpc'})
        except:
            self._disconnect()
            raise

        return connstring

    def _connect_direct(self, connection_string):
        args = {}
        args['connection_string'] = connection_string

        result = self.send('connect_direct', args)
        self._connection_id = result['connection_id']

        try:
            result = self.send('open_interface', {'interface': 'rpc'})
        except:
            self._disconnect()
            raise

    def _enable_streaming(self):
        self.send('open_interface', {'interface': 'streaming'})
        return self._report_queue

    def _enable_broadcasting(self):
        self._broadcast_queue = Queue()
        return self._broadcast_queue

    def _send_rpc(self, address, feature, cmd, payload, **kwargs):
        args = {}
        args['rpc_address'] = address
        args['rpc_feature'] = feature
        args['rpc_command'] = cmd
        args['rpc_payload'] = str(payload)

        timeout = 3.0
        if 'timeout' in kwargs:
            timeout = float(kwargs['timeout'])

        args['rpc_timeout'] = timeout

        result = self.send('send_rpc', args)
        status = result['status']
        payload = result['payload']

        return status, payload

    def _disconnect(self):
        self.send('disconnect')

    def _report_callback(self, report):
        if isinstance(report, BroadcastReport):
            if self._broadcast_queue is None:
                return

            self._broadcast_queue.put(report)
        else:
            self._report_queue.put(report)

    def send(self, command, args=None, progress=None):
        cmd = {}
        cmd['command'] = command

        if args is None:
            args = {}

        cmd.update(args)

        msg = msgpack.packb(cmd, use_bin_type=True)
        if self.binary is False:
            msg = base64.standard_b64encode(msg)

        self.client.send(msg, binary=self.binary)

        done = False

        while not done:
            try:
                result = self.client.messages.get(timeout=10.0)
            except Empty:
                raise TimeoutExpiredError('Timeout waiting for response to %s command from websocket server' % command)

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
