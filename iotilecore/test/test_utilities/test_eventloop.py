"""Tests for the shared background EventLoop."""

import asyncio
import pytest
from iotile.core.utilities.event_loop import BackgroundEventLoop
from iotile.core.exceptions import TimeoutExpiredError


@pytest.fixture(scope="function")
def clean_loop():
    """Create and cleanly stop a background loop."""

    loop = BackgroundEventLoop()
    loop.start()

    yield loop

    loop.stop()


def test_basic_functionality():
    """Ensure that EventLoops works at a basic level."""


    loop = BackgroundEventLoop()
    loop.start()

    try:
        async def _loop_task():
            return loop.inside_loop()

        assert loop.run_coroutine(_loop_task()) is True

        async def _failing_task():
            raise ValueError("hello")

        with pytest.raises(ValueError):
            loop.run_coroutine(_failing_task())
    finally:
        loop.stop()


def test_primary_task_cleanup():
    """Make sure tasks are properly cleaned up."""

    loop = BackgroundEventLoop()
    loop.start()

    try:
        async def _cor():
            await asyncio.sleep(15)

        primary = loop.add_task(_cor, "test_task")
        assert primary.name == 'test_task'
    finally:
        loop.stop()

    assert primary.task.cancelled() is True
    assert primary.task.done() is True


def test_task_cleanup_failure(clean_loop):
    """Make sure we don't deadlock if a task's cleanup routine doesn't work."""

    async def _cor():
        await asyncio.sleep(15)

    primary = clean_loop.add_task(_cor(), "test_task", finalizer=lambda x: None, stop_timeout=0.01)
    with pytest.raises(TimeoutExpiredError):
        primary.stop_threadsafe()

    # If there's a timeout, the task is cancelled
    assert primary.stopped
    assert primary.task.done()
    assert primary.task.cancelled()


def test_subtasks(clean_loop):
    """Make sure we don't deadlock if a task's cleanup routine doesn't work."""

    event = clean_loop.create_event()

    async def _primary():
        try:
            await asyncio.sleep(15)
        except asyncio.CancelledError:
            event.set()

    async def _sub():
        await event.wait()

    primary = clean_loop.add_task(_primary(), "test_task")
    subtask = clean_loop.add_task(_sub(), "sub_task", parent=primary)

    assert len(primary.subtasks) == 1

    primary.stop_threadsafe()

    assert primary.stopped
    assert primary.task.done()
    assert not primary.task.cancelled()

    assert subtask.task.done()
    assert not subtask.task.cancelled()


def test_subtasks_nocleanup(clean_loop):
    """Make sure we cancel subtasks if the parent doesn't clean them up."""

    event = clean_loop.create_event()

    async def _primary():
        try:
            await asyncio.sleep(15)
        except asyncio.CancelledError:
            pass

    async def _sub():
        await event.wait()

    primary = clean_loop.add_task(_primary(), "test_task", stop_timeout=0.01)
    subtask = clean_loop.add_task(_sub(), "sub_task", parent=primary)

    assert len(primary.subtasks) == 1

    with pytest.raises(TimeoutExpiredError):
        primary.stop_threadsafe()

    assert primary.stopped
    assert primary.task.done()
    assert not primary.task.cancelled()

    assert subtask.task.done()
    assert subtask.task.cancelled()
