"""A websocket handler for getting status information
"""

import logging
import datetime
import tornado.websocket
import tornado.gen
import msgpack
from command_formats import CommandMessage
from iotile.core.exceptions import ArgumentError, ValidationError


class ServiceWebSocketHandler(tornado.websocket.WebSocketHandler):
    _logger = logging.getLogger('service.query')

    def initialize(self, manager):
        self.manager = manager

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

    def on_message(self, message):
        cmd = self.unpack(message)

        try:
            CommandMessage.verify(cmd)
            self._on_command(cmd)
        except ValidationError:
            self.send_error('message did not correspond with a known schema')

    def _on_command(self, cmd):
        """Process a command to the status server

        The command is previously validated in on_message
        """

        op = cmd['operation']

        if op == 'heartbeat':
            try:
                self.manager.send_heartbeat(cmd['name'])
                self.send_response(True, None)
            except Exception, exc:
                self.send_error(str(exc))
        elif op == 'list_services':
            names = self.manager.list_services()
            self.send_response(True, {'services': names})
        elif op == 'query_status':
            try:
                status = self.manager.query_status(cmd['name'])
                self.send_response(True, status)
            except ArgumentError:
                self.send_error("Service name could not be found")
        else:
            self.send_error("Unknown command: %s" % op)

    def send_response(self, success, obj):
        """Send a response back to someone
        """

        resp_object = {'type': 'response', 'success': success}
        if obj is not None:
            resp_object['payload'] = obj

        msg = msgpack.packb(resp_object, default=self.encode_datetime)

        try:
            self.write_message(msg, binary=True)
        except tornado.websocket.WebSocketClosedError:
            pass

    def send_error(self, reason):
        """Send an error to someone
        """

        msg = msgpack.packb({'type': 'response', 'success': False, 'reason': reason})

        try:
            self.write_message(msg, binary=True)
        except tornado.websocket.WebSocketClosedError:
            pass

    def open(self, *args):
        self.stream.set_nodelay(True)
        self._logger.info('Client connected')

    def on_close(self, *args):
        self._logger.info('Client disconnected')
