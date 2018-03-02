"""Set config statement that adds a config variable to the sensor graph."""

from future.utils import python_2_unicode_compatible
from .statement import SensorGraphStatement
from iotile.sg import SlotIdentifier
from iotile.sg.exceptions import SensorGraphSemanticError, UnresolvedIdentifierError


@python_2_unicode_compatible
class SetConfigStatement(SensorGraphStatement):
    """A config variable assignment.

    The statement form is:
    set var = value [as type];

    where var must be an identifier or a number and value must be an rvalue.
    If var is not an identifier that corresponds with a known ConfigDefinition
    that specifies the type of the config variable, the type must be specified
    explicitly.

    Args:
        parsed(ParseResults): The parsed tokens that make up this
            statement.
        location (LocationInfo): A namedtuple with information on the line this
            statement was generated from so that we can log appropriate error
            messages.
    """

    def __init__(self, parsed, location=None):
        self.identifier = parsed[0]
        self.value = parsed[1]
        self.explicit_type = None

        if len(parsed) == 3:
            self.explicit_type = parsed[2]

        super(SetConfigStatement, self).__init__([], location)

    def __str__(self):
        if self.explicit_type is not None:
            return u"set %s = %s as %s;" % (str(self.identifier), str(self.value), str(self.explicit_type))

        return u"set %s = %s" % (str(self.identifier), str(self.value))

    def execute(self, sensor_graph, scope_stack):
        """Execute this statement on the sensor_graph given the current scope tree.

        This adds a single config variable assignment to the current sensor graph

        Args:
            sensor_graph (SensorGraph): The sensor graph that we are building or
                modifying
            scope_stack (list(Scope)): A stack of nested scopes that may influence
                how this statement allocates clocks or other stream resources.
        """

        parent = scope_stack[-1]

        try:
            slot = parent.resolve_identifier('current_slot', SlotIdentifier)
        except UnresolvedIdentifierError:
            raise SensorGraphSemanticError("set config statement used outside of config block")

        if self.explicit_type is None or not isinstance(self.identifier, int):
            raise SensorGraphSemanticError("Config variable type definitions are not yet supported")

        if isinstance(self.value, (bytes, bytearray)) and not self.explicit_type == 'binary':
            raise SensorGraphSemanticError("You must pass the binary variable type when using encoded binary data")

        if not isinstance(self.value, (bytes, bytearray)) and self.explicit_type == 'binary':
            raise SensorGraphSemanticError("You must pass an encoded binary value with binary type config variables")

        sensor_graph.add_config(slot, self.identifier, self.explicit_type, self.value)
