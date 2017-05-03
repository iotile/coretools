import logging
import datetime
import tornado.websocket
import tornado.gen
import msgpack


class WebSocketHandler(tornado.websocket.WebSocketHandler):
    _logger = logging.getLogger('ws.handler')
    connection = None

    def initialize(self, manager):
        self.manager = manager
        self.report_monitor = None

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
            obj = {'__datetime__': True, 'as_str': obj.strftime("%Y%m%dT%H:%M:%S.%fZ").encode()}
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
            resp = yield self.manager.connect(cmd['uuid'])

            if resp['success']:
                self.connection = resp['connection_id']
                self.report_monitor = self.manager.register_monitor(cmd['uuid'], ['report'], self._notify_report_sync)

            self.send_response(resp)
        elif cmdcode == 'connect_direct':
            resp = yield self.manager.connect_direct(cmd['connection_string'])
            if resp['success']:
                self.connection = resp['connection_id']

            self.send_response(resp)
        elif cmdcode == 'disconnect':
            if self.connection is not None:
                resp = yield self.manager.disconnect(self.connection)

                if resp['success']:
                    self.connection = None
                    if self.report_monitor is not None:
                        self.manager.remove_monitor(self.report_monitor)
                        self.report_monitor = None

                self.send_response(resp)
            else:
                self.send_error('Disconnection when there was no connection')
        elif cmdcode == 'open_interface':
            if self.connection is not None:
                resp = yield self.manager.open_interface(self.connection, cmd['interface'])
                self.send_response(resp)
            else:
                self.send_error('Attempt to open IOTile interface when there was no connection')
        elif cmdcode == 'send_rpc':
            if self.connection is not None:
                resp = yield self.manager.send_rpc(self.connection, cmd['rpc_address'], cmd['rpc_feature'], cmd['rpc_command'], bytearray(cmd['rpc_payload']), cmd['rpc_timeout'])
                self.send_response(resp)
            else:
                self.send_error('Attempt to send an RPC when there was no connection')
        elif cmdcode == 'send_script':
            if self.connection is not None:
                resp = yield self.manager.send_script(self.connection, cmd['data'], lambda x, y:self._notify_progress_async(tornado.ioloop.IOLoop.current(), x, y))
                self.send_response(resp)
            else:
                self.send_error('Attempt to send an RPC when there was no connection')
        else:
            self.send_error('Command %s not supported' % cmdcode)

    def _notify_progress_async(self, loop, current, total):
        loop.add_callback(self._notify_progress_sync, current, total)

    def _notify_progress_sync(self, current, total):
        self.send_response({'type':'progress', 'current': current, 'total':total})

    def _notify_report_sync(self, device_uuid, event_name, report):
        self.send_response({'type':'report', 'value': report.serialize()})

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
            resp = yield self.manager.disconnect(self.connection)
            self.connection = None

        if self.report_monitor is not None:
            self.manager.remove_monitor(self.report_monitor)
            self.report_monitor = None

        self._logger.info('Client disconnected')
