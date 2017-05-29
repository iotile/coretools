"""On blocks trigger functions when an event occurs on a stream."""

from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement


@python_2_unicode_compatible
class OnBlock(SensorGraphStatement):
    """A block of statements that should run every time an event occurs

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        children(list(SensorGraphStatement)): The statements that are
            part of this on block.
    """

    def __init__(self, parsed, children):

        self.ident_or_stream = parsed[0]

        super(OnBlock, self).__init__(children)

    def __str__(self):
        return u"on %s" % (str(self.ident_or_stream),)
