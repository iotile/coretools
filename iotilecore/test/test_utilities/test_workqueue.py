"""Tests of WorkQueueThread."""

import pytest
from iotile.core.utilities import WorkQueueThread

def _handler(arg):
    if arg == "raise":
        raise ValueError("I was told to raise an exception")

    return arg


def test_basic_usage():
    """Make sure all methods on WorkQueueThread work."""
    shared = [None, None]

    def _callback(exc_info, return_value):
        shared[0] = exc_info
        shared[1] = return_value

    workqueue = WorkQueueThread(_handler)

    workqueue.start()

    assert workqueue.dispatch('test') == 'test'

    with pytest.raises(ValueError):
        workqueue.dispatch('raise')

    # Make sure stop
    workqueue.dispatch('test 2', callback=_callback)
    workqueue.flush()
    assert shared == [None, 'test 2']

    workqueue.dispatch('test 3', callback=_callback)
    workqueue.stop()
    assert shared == [None, 'test 3']


def test_ordering():
    """Make sure results pop in the correct order."""

    shared = []

    def _callback(exc_info, return_value):
        assert exc_info is None
        shared.append(return_value)

    workqueue = WorkQueueThread(_handler)
    workqueue.start()

    for i in range(0, 5):
        workqueue.dispatch(i, callback=_callback)

    workqueue.flush()
    assert shared == [0, 1, 2, 3, 4]

    for i in range(5, 10):
        workqueue.dispatch(i, callback=_callback)

    last = workqueue.dispatch(10)
    assert shared == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert last == 10

    workqueue.stop()
