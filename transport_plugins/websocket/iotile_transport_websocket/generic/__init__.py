"""A generic bidirectional command/respond + server push framework over websockets.

Nothing inside this package is specific to the iotile communication format or
DeviceAdapters.  It is just a framework for serving callable methods over
websockets including the ability for the server to push events to a connected
client.

The generic messages that can be exchanged are defined in :mod:`messages` and
include placeholders for generic payloads.  The way to understand the
relationship between this ``generic`` subpackage and the rest of
``iotile-transport-websocket`` is that this subpackage provides the communication
layer on top of which the iotile specific websockets functionality is
implemented.
"""

from .async_client import AsyncValidatingWSClient
from .async_server import AsyncValidatingWSServer
from .errors import ServerCommandError

__all__ = ['AsyncValidatingWSServer', 'AsyncValidatingWSClient', 'ServerCommandError']
