import tornado.web
from tornado.httpserver import HTTPServer
from tornado import netutil
import socket
import logging
from wshandler import WebSocketHandler


def bind_unused_port():
    """Bind a server socket to an available port on localhost.

    Adapted from tornado source code.
    Returns:
        (socket, port)
    """
    sock = netutil.bind_sockets(None, '127.0.0.1', family=socket.AF_INET,
                                reuse_port=False)[0]
    port = sock.getsockname()[1]
    return sock, port


class WebSocketGatewayAgent(object):
    """A gateway agent for connecting to an IOTile gateway over websockets

    Args:
        manager (DeviceManager): A device manager provided
            by iotile-gateway.
        loop (IOLoop): A tornado IOLoop that this agent
            should integrate into.
        args (dict): A dictionary of arguments for configuring
            this agent.
    """

    def __init__(self, args, manager, loop):
        self._args = args
        self.app = None
        self.port = None
        self._manager = manager
        self._loop = loop
        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.NullHandler())
        self._logger.setLevel(logging.INFO)

    def start(self):
        """Start this gateway agent

        Called before the event loop is running
        """

        self.app = tornado.web.Application([
            (r'/iotile/v1', WebSocketHandler, {'manager': self._manager}),
        ])

        port = self._args.get('port', 5120)

        if port == 'unused':
            sock, port = bind_unused_port()
            server = HTTPServer(self.app, io_loop=self._loop)
            server.add_sockets([sock])
            server.start()
        else:
            self.app.listen(port)

        self.port = port
        self._logger.info("Started Websocket Agent on port %d" % port)

    def stop(self):
        """Stop this gateway agent

        Called with the event loop running
        """

        pass
