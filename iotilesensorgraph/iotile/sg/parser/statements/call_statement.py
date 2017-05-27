"""Call RPC statement."""

from .statement import SensorGraphStatement


class CallRPCStatement(SensorGraphStatement):
    """Call an RPC on a tile.

    The form of the statement should be
    call (ident|number) on slot_id

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
    """

    def __init__(self, parsed):
        self.rpc_id = parsed[0]
        self.slot_id = parsed[1]

        super(CallRPCStatement, self).__init__([])
