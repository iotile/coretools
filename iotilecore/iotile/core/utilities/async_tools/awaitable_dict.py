"""A utility class for asyncio that lets you await a dict entry."""

import asyncio

_MISSING = object()

class AwaitableDict:
    """Utility class for an async key/value store.

    This class lets you declare a key that should be set at a future point in
    time using declare(name).  Then you can wait until the key is set with an
    optional maximum timeout.  Another task or callback in the same loop can
    set the value using set() and your blocking get() call will automatically
    return the value.

    This class is useful for blocking on long-running network operations that
    have a unique identifier associated with them.  The method are optimized
    to be easy to use.  With the default keyword parameters, there is no need
    to clean anything up manually.

    Args:
        loop (asyncio.BackgroundEventLoop): The loop that this object should
            be associated with.
    """

    def __init__(self, loop):
        self._data = {}
        self._loop = loop

    def __len__(self):
        return len(self._data)

    def _ensure_declared(self, name):
        if name in self._data:
            return

        self.declare(name)

    def declare(self, name):
        """Declare that a key will be set in the future.

        This will create a future for the key that is used to
        hold its result and allow awaiting it.

        Args:
            name (str): The unique key that will be used.
        """

        if name in self._data:
            raise KeyError("Declared name {} that already existed".format(name))

        self._data[name] = self._loop.create_future()

    async def get(self, name, timeout=None, autoremove=True):
        self._ensure_declared(name)

        try:
            await asyncio.wait_for(self._data[name], timeout, loop=self._loop.get_loop())
            return self._data[name].result()
        finally:
            if autoremove:
                self._data[name].cancel()
                del self._data[name]

    def get_nowait(self, name, default=_MISSING, autoremove=False):
        self._ensure_declared(name)

        try:
            future = self._data[name]
            if future.done():
                return future.result()

            if default is _MISSING:
                raise KeyError("Key {} has not been assigned a value and no default given".format(name))

            return default
        finally:
            if autoremove:
                self._data[name].cancel()
                del self._data[name]

    def set(self, name, value, autodeclare=False):
        if not autodeclare and name not in self._data:
            raise KeyError("Key {} has not been declared and autodeclare=False".format(name))

        self._ensure_declared(name)
        self._data[name].set_result(value)
