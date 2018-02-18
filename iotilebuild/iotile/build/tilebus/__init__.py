"""TileBus RPC description parsing and compilation.

This package takes in an interface file (.bus) and compiles
it into ROM tables that can be loaded into a microcontroller
device as part of its firmware and allow you to dispatch
RPCs to C function handlers defined in that firmware.
"""

from .descriptor import TBDescriptor
from .block import TBBlock
from .handler import TBHandler

__all__ = ['TBDescriptor', 'TBBlock', 'TBHandler']
