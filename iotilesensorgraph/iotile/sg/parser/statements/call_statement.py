"""Call RPC statement."""

from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement


@python_2_unicode_compatible
class CallRPCStatement(SensorGraphStatement):
    """Call an RPC on a tile.

    The form of the statement should be
    call (ident|number) on slot_id => stream

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
    """

    def __init__(self, parsed):
        self.rpc_id = parsed[0]
        self.slot_id = parsed[1]
        self.stream = parsed[2]

        super(CallRPCStatement, self).__init__([])

    def __str__(self):
        return u'call 0x%X on %s => %s;' % (self.rpc_id, str(self.slot_id), str(self.stream))
