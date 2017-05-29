"""Blocks that execute when someone is connected."""

from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement


@python_2_unicode_compatible
class WhenBlock(SensorGraphStatement):
    """A block of statements that should run when someone is connected to the device.

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        children(list(SensorGraphStatement)): The statements that are
            part of this when block.
    """

    def __init__(self, parsed, children):
        self.slot_id = parsed[0]

        super(WhenBlock, self).__init__(children)

    def __str__(self):
        return u"when connected to %s" % (str(self.slot_id),)
