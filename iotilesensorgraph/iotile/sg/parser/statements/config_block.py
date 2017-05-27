"""Configuration block for assigning config variables to a tile."""

from .statement import SensorGraphStatement


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
