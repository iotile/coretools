"""Configuration block for assigning config variables to a tile."""

from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement


@python_2_unicode_compatible
class ConfigBlock(SensorGraphStatement):
    """A block of config variables to assign to a tile.

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        children(list(SensorGraphStatement)): The statements that are
            part of this config block.
    """

    def __init__(self, parsed, children):
        self.slot = parsed[0]

        super(ConfigBlock, self).__init__(children)

    def __str__(self):
        return u"config {}".format(self.slot)
