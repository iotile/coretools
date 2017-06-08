from .meta_statement import MetaStatement
from .config_statement import SetConfigStatement
from .config_block import ConfigBlock
from .call_statement import CallRPCStatement
from .copy_statement import CopyStatement
from .every_block import EveryBlock
from .on_block import OnBlock
from .when_block import WhenBlock
from .streamer_statement import StreamerStatement
from .trigger_statement import TriggerStatement


# All of the known statements in a sensor graph file and their matching tag names
statement_map = {
    'meta_statement': MetaStatement,
    'set_statement': SetConfigStatement,
    'config_block': ConfigBlock,
    'call_statement': CallRPCStatement,
    'copy_statement': CopyStatement,
    'streamer_statement': StreamerStatement,
    'trigger_statement': TriggerStatement,
    'every_block': EveryBlock,
    'on_block': OnBlock,
    'when_block': WhenBlock
}

__all__ = ['statement_map']
