"""Add a data streamer to the sensor graph."""

from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement
from iotile.sg.exceptions import SensorGraphSemanticError
from iotile.sg import SlotIdentifier
from iotile.sg.streamer import DataStreamer


@python_2_unicode_compatible
class StreamerStatement(SensorGraphStatement):
    """A streamer definition that adds an output to the sensor graph.

    [manual] [encrypted|signed] [realtime] streamer on <selector> [to <slot>];

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        location (LocationInfo): A namedtuple with information on the line this
            statement was generated from so that we can log appropriate error
            messages.
    """

    def __init__(self, parsed, location=None):
        realtime = 'realtime' in parsed
        encrypted = 'security' in parsed and parsed['security'] == 'encrypted'
        signed = 'security' in parsed and parsed['security'] == 'signed'
        self.auto = 'manual' not in parsed

        self.with_other = None
        if 'with_other' in parsed:
            self.with_other = parsed['with_other']
            self.auto = False

        dest = SlotIdentifier.FromString('controller')
        if 'explicit_tile' in parsed:
            dest = parsed['explicit_tile']

        selector = parsed['selector']

        # Make sure all of the combination are valid
        if realtime and (encrypted or signed):
            raise SensorGraphSemanticError("Realtime streamers cannot be either signed or encrypted")

        super(StreamerStatement, self).__init__([], location)

        self.dest = dest
        self.selector = selector

        if realtime:
            self.report_format = u'individual'
        elif signed:
            self.report_format = u'signedlist_userkey'
        elif encrypted:
            raise SensorGraphSemanticError("Encrypted streamers are not yet supported")
        else:
            self.report_format = u'hashedlist'

    def execute(self, sensor_graph, scope_stack):
        """Execute this statement on the sensor_graph given the current scope tree.

        This adds a single DataStraemer to the current sensor graph

        Args:
            sensor_graph (SensorGraph): The sensor graph that we are building or
                modifying
            scope_stack (list(Scope)): A stack of nested scopes that may influence
                how this statement allocates clocks or other stream resources.
        """

        streamer = DataStreamer(self.selector, self.dest, self.report_format, self.auto, with_other=self.with_other)
        sensor_graph.add_streamer(streamer)

    def __str__(self):
        return u'streamer {} (format = {});'.format(self.selector, self.report_format)
