"""Slot identifier parsing of 'slot 1' into SlotIdentifier."""

from builtins import str
from future.utils import python_2_unicode_compatible
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
