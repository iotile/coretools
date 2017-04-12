import os
import tornado.gen
import tornado.testing
from tornado.httpserver import HTTPServer
from tornado import netutil
import socket
from concurrent.futures import ThreadPoolExecutor


def bind_unused_port(reuse_port=False):
    """Binds a server socket to an available port on localhost.

    Adapted from tornado source code.
    Returns a tuple (socket, port).
    """
    sock = netutil.bind_sockets(None, '127.0.0.1', family=socket.AF_INET,
                                reuse_port=reuse_port)[0]
    port = sock.getsockname()[1]
    return sock, port


def get_async_test_timeout():
    """Get the global timeout setting for async tests.

    Adapted from tornado source code.
    Returns a float, the timeout in seconds.
    """

    try:
        return float(os.environ.get('ASYNC_TEST_TIMEOUT'))
    except (ValueError, TypeError):
        return 5


class AsyncWebSocketsTestCase(tornado.testing.AsyncTestCase):
    """A test case that starts up a WebSockets server.

    Adapted from tornado source code.

    Subclasses must override `get_app()`, which returns the
    `tornado.web.Application` (or other `.HTTPServer` callback) to be tested.
    Tests will typically use the provided ``self.http_client`` to fetch
    URLs from this server.

    Subclass specific setup that requires an ioloop must be in the initialize()
    function that is called before get_app() is called.  deinitialize() is called
    after everything else is teared down.
    """

    executor = ThreadPoolExecutor(max_workers=1)

    def setUp(self):
        super(AsyncWebSocketsTestCase, self).setUp()
        sock, port = bind_unused_port()
        self.__port = port

        self.initialize()

        self._app = self.get_app()
        self.http_server = self.get_http_server()
        self.http_server.add_sockets([sock])

    def get_http_server(self):
        return HTTPServer(self._app, io_loop=self.io_loop,
                          **self.get_httpserver_options())

    def get_app(self):
        """Should be overridden by subclasses to return a
        `tornado.web.Application` or other `.HTTPServer` callback.
        """
        raise NotImplementedError()

    def initialize(self):
        pass

    def deinitialize(self):
        pass

    def get_httpserver_options(self):
        """May be overridden by subclasses to return additional
        keyword arguments for the server.
        """
        return {}

    def get_port(self):
        """Returns the port used by the server.

        A new port is chosen for each test.
        """
        return self.__port

    def get_protocol(self):
        return 'ws'

    def get_url(self, path):
        """Returns an absolute url for the given path on the test server."""
        return '%s://localhost:%s%s' % (self.get_protocol(),
                                        self.get_port(), path)

    def get_iotile_port(self):
        return 'ws:127.0.0.1:%s/iotile/v1' % (self.get_port())

    def get_supervisor_port(self):
        return 'ws://127.0.0.1:%s/services' % (self.get_port())

    def tearDown(self):
        self.http_server.stop()
        self.io_loop.run_sync(self.http_server.close_all_connections,
                              timeout=get_async_test_timeout())

        self.deinitialize()

        super(AsyncWebSocketsTestCase, self).tearDown()
