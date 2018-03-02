"""A meta variable definition that is used for passing information along with a sensor graph."""

from future.utils import python_2_unicode_compatible
from iotile.sg.exceptions import SensorGraphSemanticError
from .statement import SensorGraphStatement
from ..scopes import RootScope


@python_2_unicode_compatible
class MetaStatement(SensorGraphStatement):
    """A metadata variable definition.

    The statement form is:
    meta var = value;

    where var must be an identifier and value must be an rvalue.

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

        super(MetaStatement, self).__init__([], location)

    def __str__(self):
        return u'meta %s = %s;' % (str(self.identifier), str(self.value))

    def execute(self, sensor_graph, scope_stack):
        """Execute this statement on the sensor_graph given the current scope tree.

        This function will likely modify the sensor_graph and will possibly
        also add to or remove from the scope_tree.  If there are children nodes
        they will be called after execute_before and before execute_after,
        allowing block statements to sandwich their children in setup and teardown
        functions.

        Args:
            sensor_graph (SensorGraph): The sensor graph that we are building or
                modifying
            scope_stack (list(Scope)): A stack of nested scopes that may influence
                how this statement allocates clocks or other stream resources.
        """

        if not isinstance(scope_stack[-1], RootScope):
            raise SensorGraphSemanticError("You may only declare metadata at global scope in a sensorgraph.", identifier=self.identifier, value=self.value)

        sensor_graph.add_metadata(self.identifier, self.value)
