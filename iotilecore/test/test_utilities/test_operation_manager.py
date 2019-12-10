"""Tests of the OperationManager class."""

import asyncio
import pytest
from iotile.core.utilities.async_tools import OperationManager, BackgroundEventLoop
from iotile.core.utilities.async_tools.operation_manager import MessageSpec


@pytest.fixture(scope="function")
def op_man():
    loop = BackgroundEventLoop()

    loop.start()

    man = OperationManager(loop=loop)

    yield loop, man

    loop.stop()


def test_basic_await(op_man):
    """Make sure we can block waiting for a message."""

    loop, man = op_man

    async def block_on():
        future1 = man.wait_for(name="test", value=1, timeout=1.0)
        future2 = man.wait_for(name="test", value=1, hello=4, timeout=1.0)

        assert len(list(man.waiters())) == 2

        message = dict(name="test", hello=5, value=1)
        await man.process_message(message)

        message1 = await future1
        assert message1 == message
        assert len(list(man.waiters())) == 1

        message = dict(name="test", hello=4, value=1)
        await man.process_message(message)

        message2 = await future2
        assert message2 == message
        assert len(list(man.waiters())) == 0

    loop.run_coroutine(block_on())


def test_wait_timeout(op_man):
    """Make sure we properly time out."""
    loop, man = op_man

    with pytest.raises(asyncio.TimeoutError):
        loop.run_coroutine(man.wait_for(name="test", timeout=0.01))

    assert len(list(man.waiters())) == 0


def test_object_messages(op_man):
    """Make sure we can handle object messages."""

    loop, man = op_man

    async def block_on():
        class _Message:
            name = "test"
            value = 1
            hello = 2

        future1 = man.wait_for(name="test", value=1, timeout=1.0)

        msg = _Message()
        await man.process_message(msg)

        received = await future1
        assert msg is received

    loop.run_coroutine(block_on())


def test_persistent_callbacks(op_man):
    """Make sure we can register callbacks as well as futures."""

    loop, man = op_man

    shared = [0]

    def incrementer(_msg):
        shared[0] += 1

    handle = man.every_match(incrementer, name="msg", value=1)

    assert shared[0] == 0

    loop.run_coroutine(man.process_message(dict(name="msg", value=2)))
    assert shared[0] == 0

    loop.run_coroutine(man.process_message(dict(name="msg", value=1)))
    assert shared[0] == 1

    loop.run_coroutine(man.process_message(dict(name="msg", value=1)))
    assert shared[0] == 2

    man.remove_waiter(handle)

    loop.run_coroutine(man.process_message(dict(name="msg", value=1)))
    assert shared[0] == 2


def test_wait_many(op_man):
    loop, man = op_man

    man.pause()
    man.queue_message_threadsafe(dict(action="event", value=1))
    man.queue_message_threadsafe(dict(action="event", value=2))
    man.queue_message_threadsafe(dict(action="error"))
    man.queue_message_threadsafe(dict(action="end"))

    end_spec = MessageSpec(action="end")
    error_spec = MessageSpec(action="error")
    event_spec = MessageSpec(action="event")

    accum = loop.run_coroutine(
        man.gather_until([event_spec, end_spec, error_spec], [end_spec, error_spec],
                         unpause=True, pause=True, timeout=0.1)
    )

    assert len(accum) == 3
    assert accum[0] == dict(action="event", value=1)
    assert accum[1] == dict(action="event", value=2)
    assert accum[2] == dict(action="error")

    info = man.info()

    assert info['queue_length'] == 1
    assert info['waiter_count'] == 0
    assert info['pause_count'] == 1
