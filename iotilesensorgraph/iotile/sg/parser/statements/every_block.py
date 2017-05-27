"""Time based event block for scheduling RPCs every X interval."""

from .statement import SensorGraphStatement


class EveryBlock(SensorGraphStatement):
    """A block of statements that should run every time interval

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        children(list(SensorGraphStatement)): The statements that are
            part of this config block.
    """

    def __init__(self, parsed, children):
        self.interval = parsed[0]

        super(EveryBlock, self).__init__(children)
