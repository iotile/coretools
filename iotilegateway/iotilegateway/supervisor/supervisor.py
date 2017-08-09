"""An IOTile gateway-in-a-box that will connect to devices using device adapters and serve them using agents."""

import logging
import threading
import tornado.ioloop
from tornado.httpserver import HTTPServer
from tornado import netutil
import socket
from .ws_handler import ServiceWebSocketHandler
from .service_manager import ServiceManager


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


class IOTileSupervisor(threading.Thread):
    """A supervisor that watches and allows control of other processes

    The supervisor runs in separate thread in a tornado IOLoop and you can call the synchronous
    wait function to wait for it to quit.  It will loop forever unless you stop it by calling
    the stop() or stop_from_signal() methods.  These functions add a task to the gateway's
    event loop and implicitly call wait to synchronously wait until the gateway loop actually
    stops.


    The arguments dictionary to IOTileSupervisor class has the same format as the json parameters
    passed to the iotile-supervisr script that is just a thin wrapper around this class.

    Args:
        config (dict): The configuration of the supervisor.  There should be two keys set:
            port (int): The port that the service manager listen on
            expected_services (list): An optional list of services that you expect to be running
                on this device so that their status can be prepopulated.  Each service entry should
                be a dict with two keys:
                    short_name (str): A unique short name for the service
                    long_name (str): A longer description of the service
    """

    def __init__(self, config):
        self.loop = tornado.ioloop.IOLoop.instance()
        self.service_manager = None
        self.loaded = threading.Event()

        self._config = config
        self._logger = logging.getLogger(__name__)

        self.port = None
        if 'port' not in config:
            self._config['port'] = 9400

        if 'expected_services' not in config:
            self._config['expected_services'] = []

        super(IOTileSupervisor, self).__init__()

    def run(self):
        """Start the supervisor and run it to completion in another thread."""

        # If we have an initialization error, stop trying to initialize more things and
        # just shut down cleanly
        should_close = False

        try:
            self.service_manager = ServiceManager(self._config['expected_services'])

            port = self._config.get('port')
            app = tornado.web.Application([
                (r'/services', ServiceWebSocketHandler, {'manager': self.service_manager, 'logger': self._logger}),
            ])



            if port == 'unused':
                sock, port = bind_unused_port()
                server = HTTPServer(app, io_loop=self.loop)
                server.add_sockets([sock])
                server.start()
            else:
                app.listen(port)

            self._logger.info("Starting IOTile supervisor service over websockets on port %d", port)
            self.port = port
        except Exception:  # pylint: disable=W0703; we want to make sure nothing prevents us from completing initialization in this thread
            self._logger.exception("Error starting supervisor service")
            should_close = True

        if should_close:
            self.loop.add_callback(self._stop_loop)
        else:
            self.loop.add_callback(self._set_loaded)  # Set loaded after we start the loop so that the server is running when loaded is set

        self.loop.start()

        # The loop has been closed, finish and quit
        self._logger.critical("Done stopping loop")

    def _set_loaded(self):
        self.loaded.set()

    def _stop_loop(self):
        """Cleanly stop the gateway and close down the IOLoop.

        This function must be called only by being added to our event loop using add_callback.
        """

        self._logger.critical("Stopping supervisor")

        self.loop.stop()
        self._logger.critical('Stopping event loop and shutting down')

    def stop(self):
        """Stop the supervisor and synchronously wait for it to stop."""

        self.loop.add_callback(self._stop_loop)
        self.wait()

    def wait(self):
        """Wait for this supervisor to shut down.

        We need this special function because waiting inside
        join will cause signals to not get handled.
        """

        while self.is_alive():
            try:
                self.join(timeout=0.1)
            except IOError:
                pass  # IOError comes when this call is interrupted in a signal handler

    def stop_from_signal(self):
        """Stop the supervisr from a signal handler, not waiting for it to stop."""

        self.loop.add_callback_from_signal(self._stop_loop)
