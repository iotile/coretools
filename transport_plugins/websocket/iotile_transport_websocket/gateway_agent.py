import tornado.web
import logging
from .wshandler import WebSocketHandler


class WebSocketGatewayAgent:
    """A gateway agent for connecting to an IOTile gateway over WebSockets (v2, working with WebSocketDeviceAdapter)

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
        self._manager = manager
        self._loop = loop
        self._logger = logging.getLogger(__name__)
        self._logger.addHandler(logging.NullHandler())
        self._logger.setLevel(logging.INFO)

    def start(self):
        """Start this gateway agent

        Called before the event loop is running
        """

        port = self._args.get('port', 5120)

        self.app = tornado.web.Application([
            (r'/iotile/v2', WebSocketHandler, {'manager': self._manager, 'loop': self._loop})
        ])

        self._logger.info("Starting WebSocket Agent v2 on port %d" % port)
        self.app.listen(port)

    def stop(self):
        """Stop this gateway agent

        Called with the event loop running
        """

        pass
