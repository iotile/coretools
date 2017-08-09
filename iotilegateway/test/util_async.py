"""Asynchronous test class for running tests on tornado servers."""

import os
import tornado.gen
import tornado.testing
from tornado.httpserver import HTTPServer
from tornado import netutil
import socket
from concurrent.futures import ThreadPoolExecutor


def bind_unused_port(reuse_port=False):
    """Bind a server socket to an available port on localhost.

    Adapted from tornado source code.
    Returns:
        (socket, port)
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
        """Setup before test."""
        super(AsyncWebSocketsTestCase, self).setUp()
        sock, port = bind_unused_port()
        self.__port = port

        self._initialize()

        self._app = self._get_app()
        self.http_server = self._get_http_server()
        self.http_server.add_sockets([sock])

    def _get_http_server(self):
        return HTTPServer(self._app, io_loop=self.io_loop,
                          **self._get_httpserver_options())

    def _get_app(self):
        """Return a `tornado.web.Application` or other `.HTTPServer` callback."""
        raise NotImplementedError()

    def _initialize(self):
        pass

    def _deinitialize(self):
        pass

    @tornado.gen.coroutine
    def _preshutdown_deinitialize(self):
        pass

    def _get_httpserver_options(self):
        """Override to pass additional options to http server."""
        return {}

    def get_port(self):
        """Return the port used by the server.

        A new port is chosen for each test.
        """
        return self.__port

    def _get_protocol(self):
        return 'ws'

    def get_url(self, path):
        """Return an absolute url for the given path on the test server."""
        return '%s://localhost:%s%s' % (self._get_protocol(),
                                        self.get_port(), path)

    def get_iotile_port(self):
        """Get the iotile port string for this server."""

        return 'ws:127.0.0.1:%s/iotile/v1' % (self.get_port())

    def get_supervisor_port(self):
        """Get the supervisor server url."""
        return 'ws://127.0.0.1:%s/services' % (self.get_port())

    def tearDown(self):
        """Clean up after test."""
        yield self._preshutdown_deinitialize()
        self.http_server.stop()
        self.io_loop.run_sync(self.http_server.close_all_connections,
                              timeout=get_async_test_timeout())

        self._deinitialize()
        super(AsyncWebSocketsTestCase, self).tearDown()
