"""A sparse memory map for debugging purposes
"""

from collections import namedtuple
import binascii
import string
from iotile.core.exceptions import ArgumentError


MemorySegment = namedtuple('MemorySegment', ['start_address', 'end_address', 'length', 'data'])
DisjointSegment = namedtuple('DisjointSegment', [])
OverlappingSegment = namedtuple('OverlappingSegment', [])

class SparseMemory(object):
    """A sparse memory map for debugging purposes

    You can add memory segments into the memory map
    a little bit at a time and decode any section into
    a python object using registered decoder functions.
    """
    def __init__(self):
        self._segments = []

    def add_segment(self, address, data, overwrite=False):
        """Add a contiguous segment of data to this memory map

        If the segment overlaps with a segment already added , an
        ArgumentError is raised unless the overwrite flag is True.

        Params:
            address (int): The starting address for this segment
            data (bytearray): The data to add
            overwrite (bool): Overwrite data if this segment overlaps
                with one previously added.
        """

        seg_type = self._classify_segment(address, len(data))
        if not isinstance(seg_type, DisjointSegment):
            raise ArgumentError("Unsupported segment type")

        segment = MemorySegment(address, address+len(data)-1, len(data), bytearray(data))
        self._segments.append(segment)

    def _create_slice(self, key):
        """Create a slice in a memory segment corresponding to a key."""

        if isinstance(key, slice):
            step = key.step
            if step is None:
                step = 1

            if step != 1:
                raise ArgumentError("You cannot slice with a step that is not equal to 1", step=key.step)

            start_address = key.start
            end_address = key.stop - 1

            start_i, start_seg = self._find_address(start_address)
            end_i, _end_seg = self._find_address(end_address)

            if start_seg is None or start_i != end_i:
                raise ArgumentError("Slice would span invalid data in memory", start_address=start_address, end_address=end_address)

            block_offset = start_address - start_seg.start_address
            block_length = end_address - start_address + 1

            return start_seg, block_offset, block_offset + block_length
        elif isinstance(key, int):
            start_i, start_seg = self._find_address(key)
            if start_seg is None:
                raise ArgumentError("Requested invalid address", address=key)

            return start_seg, key - start_seg.start_address, None
        else:
            raise ArgumentError("Unknown type of address key", address=key)

    def __getitem__(self, key):
        seg, start, end = self._create_slice(key)

        if end is None:
            return seg.data[start]

        return seg.data[start:end]

    def __setitem__(self, key, item):
        seg, start, end = self._create_slice(key)

        if end is None:
            seg.data[start] = item
        else:
            seg.data[start:end] = item

    @classmethod
    def _in_segment(cls, address, segment):
        return address >= segment.start_address and address <= segment.end_address

    def _find_address(self, address):
        for i, segment in enumerate(self._segments):
            if self._in_segment(address, segment):
                return i, segment

        return -1, None

    def _classify_segment(self, address, length):
        """Determine how a new data segment fits into our existing world

        Params:
            address (int): The address we wish to classify
            length (int): The length of the segment

        Returns:
            int: One of SparseMemoryMap.prepended
        """

        end_address = address + length - 1

        _, start_seg = self._find_address(address)
        _, end_seg = self._find_address(end_address)

        if start_seg is not None or end_seg is not None:
            raise ArgumentError("Overlapping segments are not yet supported", address=address, length=length)

        return DisjointSegment()

    @classmethod
    def _iter_groups(cls, data, chunk_length):
        for i in xrange(0, len(data), chunk_length):
            yield data[i:i+chunk_length]

    @classmethod
    def _format_line(cls, start_address, data):
        hexdata = binascii.hexlify(data)
        spaced_hex = ' '.join([hexdata[i:i+2] for i in xrange(0, len(hexdata), 2)])
        separated_hex = spaced_hex[0:len(spaced_hex)/2] + ' ' + spaced_hex[len(spaced_hex)/2:]

        asciidata = ''

        for x in data:
            if chr(x) in string.printable and chr(x) != '\n' and chr(x) != '\r' and chr(x) != '\t':
                asciidata += chr(x)
            else:
                asciidata += '.'

        return "0x{:08x}: {}  {}".format(start_address, separated_hex, asciidata)

    def __str__(self):
        """Convert to string as a 64 byte wide hex dump
        """

        stringdata = ""

        for segment in self._segments:
            # Insert a ... between every distinct segment
            if len(stringdata) > 0:
                stringdata += ("----- "*13) + "\n"

            current_addr = segment.start_address
            for linedata in self._iter_groups(segment.data, 16):
                line = self._format_line(current_addr, linedata)
                stringdata += line + '\n'
                current_addr += 16

        return stringdata
