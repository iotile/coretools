"""Response objects that allow synchronously waiting for things from the EmulationLoop.

There are two kinds of Response objects: AwaitableResponse that wraps a Future
object for use from a coroutine and CrossThreadResponse that is for waiting
for a response from the event loop by another thread.

Their APIs are identical so that they can be used interchangeably.
"""

import sys
import threading
import asyncio

from iotile.core.exceptions import InternalError, TimeoutExpiredError

class GenericResponse:
    """Base class for asynchronous operation responses."""

    def __init__(self):
        self._result = None
        self._exception = None

    def set_result(self, result):
        """Finish this response and set the result."""

        if self.is_finished():
            raise InternalError("set_result called on finished AsynchronousResponse",
                                result=self._result, exception=self._exception)

        self._result = result
        self.finish()

    def set_exception(self, exc_class, exc_info, exc_stack):
        """Set an exception as the result of this operation.

        Args:
            exc_class (object): The exception type """

        if self.is_finished():
            raise InternalError("set_exception called on finished AsynchronousResponse",
                                result=self._result, exception=self._exception)

        self._exception = (exc_class, exc_info, exc_stack)
        self.finish()

    def capture_exception(self):
        """Capture the current exception context."""

        self.set_exception(*sys.exc_info())

    # Implementation from future.utils.raise_
    def _raise_exception(self):
        if self._exception is None:
            raise InternalError("No exception stored in call to _raise_exception")

        exc_type, value, traceback = self._exception
        if value is not None and isinstance(exc_type, Exception):
            raise TypeError("instance exception may not have a separate value")

        exc = value

        if exc.__traceback__ is not traceback:
            raise exc.with_traceback(traceback)

        raise exc

    def finish(self):
        """Finish this operation without any value."""
        raise NotImplementedError()

    def is_finished(self):
        """Check if this operation is finished.

        Returns:
            bool: True if the operation is finished.
        """
        raise NotImplementedError()


class CrossThreadResponse(GenericResponse):
    """A cross-thread future object that can be waited on.

    This object encapsulates returning a response from the EmulationLoop to a
    caller in a different thread.  It is waitable and can pass either a result
    or an exception, which is raised in the calling thread.
    """

    def __init__(self):
        super(CrossThreadResponse, self).__init__()
        self._finished = threading.Event()
        self._callbacks = []

    def finish(self):
        self._finished.set()

        if len(self._callbacks) > 0:
            for callback in self._callbacks:
                callback(self._exception, self._result)

    def add_callback(self, callback):
        """TEMPORARY METHOD"""
        self._callbacks.append(callback)

    def is_finished(self):
        return self._finished.is_set()

    def wait(self, timeout=None):
        """Wait for this operation to finish.

        You can specify an optional timeout that defaults to no timeout if
        None is passed.  The result of the operation is returned from this
        method. If the operation raised an exception, it is reraised from this
        method.

        Args:
            timeout (float): The maximum number of seconds to wait before timing
                out.
        """

        flag = self._finished.wait(timeout=timeout)
        if flag is False:
            raise TimeoutExpiredError("Timeout waiting for response to event loop operation")

        if self._exception is not None:
            self._raise_exception()

        return self._result


class AwaitableResponse(GenericResponse):
    """Asynchronous response for use inside the event loop."""

    def __init__(self):
        super(AwaitableResponse, self).__init__()
        self._future = asyncio.get_event_loop().create_future()

    def finish(self):
        self._future.set_result(None)

    def is_finished(self):
        return self._future.done()

    async def wait(self, timeout=None):
        """Wait for this operation to finish.

        You can specify an optional timeout that defaults to no timeout if
        None is passed.  The result of the operation is returned from this
        method. If the operation raised an exception, it is reraised from this
        method.

        Args:
            timeout (float): The maximum number of seconds to wait before timing
                out.
        """

        await asyncio.wait_for(self._future, timeout)

        if self._exception is not None:
            self._raise_exception()

        return self._result
