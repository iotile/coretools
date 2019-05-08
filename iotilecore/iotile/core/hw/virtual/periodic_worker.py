"""Base class for objects that have a background runnable task like virtual devices and tiles."""

import asyncio
import logging
import inspect
from iotile.core.exceptions import InternalError
from iotile.core.utilities.async_tools import SharedLoop, BackgroundTask


class _PeriodicWorkerMixin:
    """A simple mixin class that can run periodic callbacks in coroutines.

    This is not designed to be a general purpose class and requires that
    the class it is mixed into have a _loop and _started property.
    """

    def __init__(self):
        self._queued_workers = []
        self._workers = []

    def create_worker(self, func, interval, *args, **kwargs):
        """Spawn a worker thread running func.

        The worker will be automatically be started when start() is called and
        terminated when stop() is called on this object. This must be called
        only from the main thread.

        ``create_worker`` must not be called after stop() has been called.  If
        it is called before start() is called, the worker is started when
        start() is called, otherwise it is started immediately.

        Args:
            func (callable): Either a function that will be called in a loop
                with a sleep of interval seconds with *args and **kwargs or
                a generator function that will be called once and expected to
                yield periodically so that the worker can check if it should
                be killed.  If the function returns an awaitable, it will be
                awaited before sleeping again
            interval (float): The time interval between invocations of func.
                This should not be 0 so that the thread doesn't peg the CPU
                and should be short enough so that the worker checks if it
                should be killed in a timely fashion.
            *args: Arguments that are passed to func as positional args
            **kwargs: Arguments that are passed to func as keyword args
        """

        worker = (func, interval, args, kwargs)

        if not self._started:
            self._queued_workers.append(worker)
            return

        self._start_worker(worker)

    def _start_worker(self, worker):
        func, interval, args, kwargs = worker
        task = BackgroundTask(_worker_main(func, interval, args, kwargs), loop=self._loop)
        self._workers.append(task)

    def start_workers(self):
        """Start running this virtual device including any necessary worker threads."""

        for worker in self._queued_workers:
            self._start_worker(worker)

    def stop_workers(self):
        """Synchronously stop any potential workers."""

        for worker in self._workers:
            worker.stop_threadsafe()


async def _worker_main(func, interval, args, kwargs):
    logger = logging.getLogger(__name__)

    try:
        while True:
            await asyncio.sleep(interval)

            try:
                res = func(*args, **kwargs)
                if inspect.isawaitable(res):
                    await res
            except asyncio.CancelledError:
                raise
            except:  #pylint:disable=bare-except; We want to capture all errors in the background worker
                logger.exception("Error running background worker %s with args=%s, kwargs=%s", func, args, kwargs)
    except asyncio.CancelledError:
        pass
    except:
        logger.exception("Unknown exception in background worker")
        raise
