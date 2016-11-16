import tornado.websocket
import logging
import msgpack
import datetime
import tornado.gen
from tornado.concurrent import Future

class WebSocketHandler(tornado.websocket.WebSocketHandler):
    _logger = logging.getLogger('ws.handler')
    connection = None

    def initialize(self, manager):
        self.manager = manager

    def open(self, *args):
        self.stream.set_nodelay(True)
        self._logger.info('Client connected')

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

    def unpack(self, message):
        return msgpack.unpackb(message, object_hook=self.decode_datetime)

    @tornado.gen.coroutine
    def on_message(self, message):
        cmd = self.unpack(message)

        if 'command' not in cmd:
            self.send_error('Protocol error, no command given')

        cmdcode = cmd['command']

        if cmdcode == 'scan':
            devs = self.manager.scanned_devices
            self.send_response({'success': True, 'devices': devs.values()})
        elif cmdcode == 'connect':
            resp = yield self._connect(cmd)

            if resp['success']:
                self.connection = resp['connection_id']

            self.send_response(resp)
        elif cmdcode == 'disconnect':
            if self.connection is not None:
                resp = yield self._disconnect(self.connection)

                if resp['success']:
                    self.connection = None
                    
                self.send_response(resp)
            else:
                self.send_error('Disconnection when there was no connection')
        else:
            self.send_error('Command %s not supported' % cmdcode)

    def _connect(self, msg):
        """Connect to an IOTile device by its uuid
        """

        return self.manager.connect(msg['uuid'])

    def _disconnect(self, conn):
        """Disconnect from the currently connected IOTile device
        """

        return self.manager.disconnect(conn)

    def send_response(self, obj):
        msg = msgpack.packb(obj, default=self.encode_datetime)

        try:
            self.write_message(msg, binary=True)
        except tornado.websocket.WebSocketClosedError as err:
            pass

    def send_error(self, reason):
        msg = msgpack.packb({'success': False, 'reason': reason})
        
        try:
            self.write_message(msg, binary=True)
        except tornado.websocket.WebSocketClosedError as err:
            pass

    @tornado.gen.coroutine
    def on_close(self):
        if self.connection is not None:
            resp = yield self._disconnect(self.connection)
            self.connection = None

        self._logger.info('Client disconnected')
