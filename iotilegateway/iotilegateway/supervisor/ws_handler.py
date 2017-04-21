"""A websocket handler for managing running services."""

import logging
import datetime
import tornado.websocket
import tornado.gen
import msgpack
from command_formats import CommandMessage
from iotile.core.exceptions import ArgumentError, ValidationError


class ServiceWebSocketHandler(tornado.websocket.WebSocketHandler):
    """A websocket interface to ServiceManager."""

    def initialize(self, manager, logger):
        """Initialize this handler."""
        self.manager = manager
        self.logger = logger

    @classmethod
    def decode_datetime(cls, obj):
        """Decode a datetime from msgpack."""
        if b'__datetime__' in obj:
            obj = datetime.datetime.strptime(obj[b'as_str'].decode(), "%Y%m%dT%H:%M:%S.%f")
        return obj

    @classmethod
    def encode_datetime(cls, obj):
        """Encode a datetime for msgpack."""
        if isinstance(obj, datetime.datetime):
            obj = {'__datetime__': True, 'as_str': obj.strftime("%Y%m%dT%H:%M:%S.%f").encode()}
        return obj

    def unpack(self, message):
        """Unpack a binary message packed message with datetime handling."""
        return msgpack.unpackb(message, object_hook=self.decode_datetime)

    def on_message(self, message):
        """Handle a message received on the websocket."""
        cmd = self.unpack(message)

        try:
            CommandMessage.verify(cmd)
            self._on_command(cmd)
        except ValidationError:
            if 'operation' in cmd:
                print("Invalid operation received: %s" % cmd['operation'])
            self.send_error('message did not correspond with a known schema')

    def _on_command(self, cmd):
        """Process a command to the status server.

        The command is previously validated in on_message
        """

        op = cmd['operation']

        del cmd['operation']
        del cmd['type']
        self.logger.info("Received %s with payload %s", op, cmd)

        if op == 'heartbeat':
            try:
                self.manager.send_heartbeat(cmd['name'])

                if not cmd['no_response']:
                    self.send_response(True, None)
            except Exception, exc:
                if not cmd['no_response']:
                    self.send_error(str(exc))
        elif op == 'list_services':
            names = self.manager.list_services()
            if not cmd['no_response']:
                self.send_response(True, {'services': names})
        elif op == 'query_status':
            try:
                status = self.manager.service_status(cmd['name'])
                if not cmd['no_response']:
                    self.send_response(True, status)
            except ArgumentError:
                if not cmd['no_response']:
                    self.send_error("Service name could not be found")
        elif op == 'register_service':
            try:
                status = self.manager.add_service(cmd['name'], cmd['long_name'])
                if not cmd['no_response']:
                    self.send_response(True, None)
            except ArgumentError:
                if not cmd['no_response']:
                    self.send_error("Service was already registered")
        elif op == 'query_info':
            try:
                info = self.manager.service_info(cmd['name'])
                if not cmd['no_response']:
                    self.send_response(True, info)
            except ArgumentError:
                if not cmd['no_response']:
                    self.send_error("Service name could not be found")
        elif op == 'query_messages':
            try:
                msgs = self.manager.service_messages(cmd['name'])
                if not cmd['no_response']:
                    self.send_response(True, [msg.to_dict() for msg in msgs])
            except ArgumentError:
                if not cmd['no_response']:
                    self.send_error("Service name could not be found")
        elif op == 'query_headline':
            try:
                headline = self.manager.service_headline(cmd['name'])
                if not cmd['no_response']:
                    if headline is not None:
                        headline = headline.to_dict()
                    self.send_response(True, headline)
            except ArgumentError:
                if not cmd['no_response']:
                    self.send_error("Service name could not be found")
        elif op == 'update_state':
            try:
                self.manager.update_state(cmd['name'], cmd['new_status'])
                if not cmd['no_response']:
                    self.send_response(True, None)
            except ArgumentError, exc:
                if not cmd['no_response']:
                    self.send_error(str(exc))
        elif op == 'post_message':
            try:
                self.manager.send_message(cmd['name'], cmd['level'], cmd['message'])
                if not cmd['no_response']:
                    self.send_response(True, None)
            except ArgumentError, exc:
                if not cmd['no_response']:
                    self.send_error(str(exc))
        elif op == 'set_headline':
            try:
                self.manager.set_headline(cmd['name'], cmd['level'], cmd['message'])
                if not cmd['no_response']:
                    self.send_response(True, None)
            except ArgumentError, exc:
                if not cmd['no_response']:
                    self.send_error(str(exc))
        else:
            if not cmd['no_response']:
                self.send_error("Unknown command: %s" % op)

    def send_response(self, success, obj):
        """Send a response back to someone."""

        resp_object = {'type': 'response', 'success': success}
        if obj is not None:
            resp_object['payload'] = obj

        msg = msgpack.packb(resp_object, default=self.encode_datetime)

        try:
            self.write_message(msg, binary=True)
        except tornado.websocket.WebSocketClosedError:
            pass

    def send_error(self, reason):
        """Send an error to someone."""

        msg = msgpack.packb({'type': 'response', 'success': False, 'reason': reason})

        try:
            self.write_message(msg, binary=True)
        except tornado.websocket.WebSocketClosedError:
            pass

    def send_notification(self, name, change_type, change_info):
        """Send an unsolicited notification to someone."""

        notif_object = {'type': 'notification', 'operation': change_type, 'name': name}
        if change_info is not None:
            notif_object['payload'] = change_info

        msg = msgpack.packb(notif_object)

        try:
            self.write_message(msg, binary=True)
        except tornado.websocket.WebSocketClosedError:
            pass

    def open(self, *args):
        """Register that someone opened a connection."""
        self.stream.set_nodelay(True)
        self.manager.add_monitor(self.send_notification)
        self.logger.info('Client connected')

    def on_close(self, *args):
        """Register that someone closed a connection."""

        self.manager.remove_monitor(self.send_notification)
        self.logger.info('Client disconnected')
