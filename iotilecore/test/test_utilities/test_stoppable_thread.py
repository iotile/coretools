import pytest
import threading
import sys

if sys.version[0] == '2':
    import Queue as queue
else:
    import queue as queue

from iotile.core.utilities.stoppable_thread import StoppableWorkerThread
from iotile.core.exceptions import TimeoutExpiredError

def test_running_function():
    """Make sure we can run a function in the thread
    """

    items = queue.Queue()

    def thread_func(shared_queue):
        if shared_queue.qsize() == 3:
            return

        shared_queue.put(1)

    thread = StoppableWorkerThread(thread_func, timeout=0.001, args=(items,))
    thread.start()

    items.get(block=True, timeout=1.0)
    items.get(block=True, timeout=1.0)
    items.get(block=True, timeout=1.0)

    thread.stop()

def test_kwargs_function():
    """Make sure we can run a function in the thread with kwargs
    """

    items = queue.Queue()

    def thread_func(shared_queue):
        if shared_queue.qsize() == 3:
            return

        shared_queue.put(1)

    thread = StoppableWorkerThread(thread_func, timeout=0.001, kwargs={'shared_queue': items})
    thread.start()

    items.get(block=True, timeout=1.0)
    items.get(block=True, timeout=1.0)
    items.get(block=True, timeout=1.0)

    thread.stop()

def test_running_generator():
    """Make sure we can run a generator in the thread
    """

    items = queue.Queue()

    def thread_func(shared_queue):
        for i in xrange(0, 3):
            shared_queue.put(i)
            yield

    thread = StoppableWorkerThread(thread_func, timeout=0.001, args=(items,))
    thread.start()

    a = items.get(block=True, timeout=1.0)
    b = items.get(block=True, timeout=1.0)
    c = items.get(block=True, timeout=1.0)

    assert a == 0
    assert b == 1
    assert c == 2

    thread.stop()

def test_failed_stop():
    """Make sure that we can always kill a thread if it doesn't respond to stop()
    """

    def thread_func():
        while True:
            pass

    thread = StoppableWorkerThread(thread_func, timeout=0.001)
    thread.start()
    thread.wait_running(timeout=1.0)

    with pytest.raises(TimeoutExpiredError):
        thread.stop(timeout=0.01)

def test_failed_stop_force():
    """Make sure that we can always kill a thread if it doesn't respond to stop()
    """

    def thread_func():
        while True:
            pass

    thread = StoppableWorkerThread(thread_func, timeout=0.001)
    thread.start()

    thread.stop(timeout=0.01, force=True)
