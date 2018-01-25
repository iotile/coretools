"""Slot identifier parsing of 'slot 1' into SlotIdentifier."""

from __future__ import (unicode_literals, print_function, absolute_import)
from builtins import str
import struct
from future.utils import python_2_unicode_compatible, viewitems
from iotile.core.exceptions import ArgumentError


@python_2_unicode_compatible
class SlotIdentifier(object):
    """A slot identifier specifies the address of a tile on TileBus.

    Slots identifiers can be built from strings using FromString().
    The form of the string should be:

    slot <number> where number is between 1 and 31, inclusive
    or
    controller

    which indicates that this is a controller tile (implicitly slot 0)

    Args:
        slot (int): The slot number bertween 1 and 32 if this tile is not
            a controller.  The controller argument must be False if this
            argument is specified.
        controller (bool): True if this is a controller tile, in which case
            the slot number must be None.
    """

    KNOWN_MATCH_CODES = {
        0: 'match_none',
        1: 'match_slot',
        2: 'match_controller',
        3: 'match_name'
    }

    KNOWN_MATCH_NAMES = {y: x for x,y in viewitems(KNOWN_MATCH_CODES)}

    def __init__(self, slot=None, controller=False):

        if slot is not None:
            slot = int(slot)

        if controller and (slot is not None):
            raise ArgumentError("You cannot pass both a slot and controller argument to SlotIdentifier", slot=slot, controller=controller)

        if slot is not None and (slot < 1 or slot >= 32):
            raise ArgumentError("Slot number too big.  It must be between 1 and 31, inclusive", slot=slot)

        self.controller = controller
        self.slot = slot

    @property
    def address(self):
        """The address of this tile.

        Tile addresses are calculated as:
        controller: 8
        other tiles: 9 + slot (so slot 1 is 10)
        """

        if self.controller:
            return 8

        return 10 + self.slot

    @classmethod
    def FromString(cls, desc):
        """Create a slot identifier from a string description.

        The string needs to be either:

        controller
        OR
        slot <X> where X is an integer that can be converted with int(X, 0)

        Args:
            desc (str): The string description of the slot

        Returns:
            SlotIdentifier
        """

        desc = str(desc)

        if desc == u'controller':
            return SlotIdentifier(controller=True)

        words = desc.split()
        if len(words) != 2 or words[0] != u'slot':
            raise ArgumentError(u"Illegal slot identifier", descriptor=desc)

        try:
            slot_id = int(words[1], 0)
        except ValueError:
            raise ArgumentError(u"Could not convert slot identifier to number", descriptor=desc, number=words[1])

        return SlotIdentifier(slot=slot_id)

    @classmethod
    def FromEncoded(cls, bindata):
        """Create a slot identifier from an encoded binary descriptor.

        These binary descriptors are used to communicate slot targeting
        to an embedded device.  They are exactly 8 bytes in length.

        Args:
            bindata (bytes): The 8-byte binary descriptor.

        Returns:
            SlotIdentifier
        """

        if len(bindata) != 8:
            raise ArgumentError("Invalid binary slot descriptor with invalid length", length=len(bindata), expected=8, data=bindata)

        slot, match_op = struct.unpack("<B6xB", bindata)

        match_name = cls.KNOWN_MATCH_CODES.get(match_op)
        if match_name is None:
            raise ArgumentError("Unknown match operation specified in binary slot descriptor", operation=match_op, known_match_ops=cls.KNOWN_MATCH_CODES)

        if match_name == 'match_controller':
            return SlotIdentifier(controller=True)

        if match_name == 'match_slot':
            return SlotIdentifier(slot=slot)

        raise ArgumentError("Unsupported match operation in binary slot descriptor", match_op=match_name)

    def encode(self):
        """Encode this slot identifier into a binary descriptor.

        Returns:
            bytes: The 8-byte encoded slot identifier
        """

        slot = 0
        match_op = self.KNOWN_MATCH_NAMES['match_controller']

        if not self.controller:
            slot = self.slot
            match_op = self.KNOWN_MATCH_NAMES['match_slot']

        return struct.pack("<B6xB", slot, match_op)

    def __str__(self):
        if self.controller:
            return u'controller'

        return u'slot {}'.format(self.slot)

    def __hash__(self):
        return hash((self.controller, self.slot))

    def __eq__(self, other):
        if not isinstance(other, SlotIdentifier):
            return NotImplemented

        return self.controller == other.controller and self.slot == other.slot
