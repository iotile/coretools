"""Base class for objects that have a background runnable task like virtual devices and tiles."""

from iotile.core.exceptions import InternalError
from iotile.core.utilities.stoppable_thread import StoppableWorkerThread


class BaseRunnable(object):
    """A simple class that uses StoppableWorkerThreads for background tasks."""

    def __init__(self):
        super(BaseRunnable, self).__init__()

        self._workers = []
        self._started = False

    def create_worker(self, func, interval, *args, **kwargs):
        """Spawn a worker thread running func.

        The worker will be automatically be started when start() is called
        and terminated when stop() is called on this object.
        This must be called only from the main thread, not from a worker thread.

        create_worker must not be called after stop() has been called.  If it
        is called before start() is called, the thread is started when start()
        is called, otherwise it is started immediately.

        Args:
            func (callable): Either a function that will be called in a loop
                with a sleep of interval seconds with *args and **kwargs or
                a generator function that will be called once and expected to
                yield periodically so that the worker can check if it should
                be killed.
            interval (float): The time interval between invocations of func.
                This should not be 0 so that the thread doesn't peg the CPU
                and should be short enough so that the worker checks if it
                should be killed in a timely fashion.
            *args: Arguments that are passed to func as positional args
            **kwargs: Arguments that are passed to func as keyword args
        """

        thread = StoppableWorkerThread(func, interval, args, kwargs)
        self._workers.append(thread)

        if self._started:
            thread.start()

    def start_workers(self):
        """Start running this virtual device including any necessary worker threads."""

        if self._started:
            raise InternalError("The method start() was called twice on a BaseRunnable object.")

        self._started = True

        for worker in self._workers:
            worker.start()

    def stop_workers(self):
        """Synchronously stop any potential workers."""

        self._started = False

        for worker in self._workers:
            worker.stop()

    def stop_workers_async(self):
        """Signal that all workers should stop without waiting."""

        self._started = False
        for worker in self._workers:
            worker.signal_stop()

    def wait_workers_stopped(self):
        """Wait for all workers to stop."""

        for worker in self._workers:
            worker.wait_stopped()
