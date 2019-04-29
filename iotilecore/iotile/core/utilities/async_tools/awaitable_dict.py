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
        """Wait for a value to be set for a key.

        This is the primary way to receive values from AwaitableDict.
        You pass in the name of the key you want to wait for, the maximum
        amount of time you want to wait and then you can await the result
        and it will resolve to value from the call to set or an
        asyncio.TimeoutError.

        You should generally leave autoremove as the default True value. This
        causes the key to be removed from the dictionary after get returns.
        Normally you have a single user calling ``get`` and another calling
        ``set`` so you want to automatically clean up after the getter
        returns, no matter what.

        If the key has not already been declared, it will be declared
        automatically inside this function so it is not necessary to call
        :meth:`declare` manually in most use cases.

        Args:
            name (str): The name of the key to wait on.
            timeout (float): The maximum timeout to wait.
            autoremove (bool): Whether to automatically remove the
                key when get() returns.

        Returns:
            object: Whatever was set in the key by :meth:`set`.

        Raises:
            asyncio.TimeoutError: The key was not set within the timeout.
        """

        self._ensure_declared(name)

        try:
            await asyncio.wait_for(self._data[name], timeout, loop=self._loop.get_loop())
            return self._data[name].result()
        finally:
            if autoremove:
                self._data[name].cancel()
                del self._data[name]

    def get_nowait(self, name, default=_MISSING, autoremove=False):
        """Get the value of a key if it is already set.

        This method allows you to check if a key has already been set
        without blocking.  If the key has not been set you will get the
        default value you pass in or KeyError() if no default is passed.

        When this method returns the key is automatically removed unless
        you pass ``autoremove=False``.

        This method is not a coroutine and does not block.

        Args:
            name (str): The name of the key to wait on.
            default (object): The default value to return if the key
                has not yet been set.  Defaults to raising KeyError().
            autoremove (bool): Whether to automatically remove the
                key when get() returns.

        Returns:
            object: Whatever was set in the key by :meth:`set`.
        """

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
        """Set the value of a key.

        This method will cause anyone waiting on a key (and any future
        waiters) to unblock and be returned the value you pass here.

        If the key has not been declared previously, a KeyError() is
        raised unless you pass ``autodeclare=True`` which will cause
        the key to be declared.  Normally you don't want to autodeclare.

        This method is not a coroutine and does not block.

        Args:
            name (str): The key to set
            value (object): The value to set
            autodeclare (bool): Whether to automatically declare the
                key if is has not already been declared.  Defaults to
                False.
        """

        if not autodeclare and name not in self._data:
            raise KeyError("Key {} has not been declared and autodeclare=False".format(name))

        self._ensure_declared(name)
        self._data[name].set_result(value)
