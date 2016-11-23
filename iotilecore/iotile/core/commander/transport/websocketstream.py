from ws4py.client.threadedclient import WebSocketClient
from iotilecore.commander.exceptions import *
from iotilecore.exceptions import *
from iotilecore.commander.commands import RPCCommand
import threading
from Queue import Queue, Empty
from cmdstream import CMDStream 
import msgpack
import datetime
import time

class WSIOTileClient(WebSocketClient):
    def __init__(self, port):
        super(WSIOTileClient, self).__init__(port, protocols=['iotile-ws'])
        self.connection_established = threading.Event()
        self.messages = Queue()

    def start(self):
        self.connect()
        self.connection_established.wait()

    def opened(self):
        self.connection_established.set()

    def closed(self, code, reason):
        self.connection_established.clear()

    def received_message(self, message):
        self.messages.put(message.data)


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
        self.client = WSIOTileClient(port)
        self.client.start()
        self._connection_id = None

        CMDStream.__init__(self, port, connection_string, record=record)

    def _close(self):
        if self.client.connection_established.is_set():
            self.client.close()

    def _scan(self):
        result = self.send('scan')
        return result['devices']

    def _connect(self, uuid_value):
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

    def send(self, command, args={}, progress=None):
        cmd = {}
        cmd['command'] = command
        cmd.update(args)

        self.client.send(msgpack.packb(cmd), binary=True)

        done = False
        #start_time = time.time()

        while not done:
            try:
                resp = self.client.messages.get(timeout=10.0)
            except Empty:
                raise TimeoutError('Timeout waiting for response to %s command from websocket server' % command)

            result = self.unpack(resp)
            if 'type' in result and result['type'] == 'progress':
                total = result['total']
                current = result['current']

                if progress:
                    progress(current, total)
            else:
                done = True

        if result['success'] != True:
            raise HardwareError("Error procesing command", reason=result['reason'])

        return result

    def _send_highspeed(self, data, progress_callback):
        self.send('send_script', {'data': str(data)}, progress=progress_callback)

    def unpack(self, msg):
        return msgpack.unpackb(msg, object_hook=self.decode_datetime)

    @classmethod
    def decode_datetime(cls, obj):
        if b'__datetime__' in obj:
            obj = datetime.datetime.strptime(obj[b'as_str'].decode(), "%Y%m%dT%H:%M:%S.%f")
        return obj

    @classmethod
    def encode_datetime(cls, obj):
        if isinstance(obj, datetime.datetime):
            obj = {'__datetime__': True, 'as_str': obj.strftime("%Y%m%dT%H:%M:%S.%f").encode()}
        return obj
