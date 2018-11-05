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
