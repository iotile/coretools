"""Time based event block for scheduling RPCs every X interval."""

from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement


@python_2_unicode_compatible
class EveryBlock(SensorGraphStatement):
    """A block of statements that should run every time interval

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        children(list(SensorGraphStatement)): The statements that are
            part of this every block.
    """

    def __init__(self, parsed, children):
        self.interval = parsed[0]

        super(EveryBlock, self).__init__(children)

    def __str__(self):
        return u"every %s" % (str(self.interval),)