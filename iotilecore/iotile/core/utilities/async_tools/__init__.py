"""Utilities for simplifying async operations.

This subpackage contains a number of general utility classes for working with
complex asynchronous operations on top of the asyncio package.
"""

from .event_loop import BackgroundEventLoop, SharedLoop, BackgroundTask
from .operation_manager import OperationManager
from .awaitable_dict import AwaitableDict

__all__ = ['BackgroundEventLoop', 'SharedLoop', 'OperationManager',
           'AwaitableDict', 'BackgroundTask']
