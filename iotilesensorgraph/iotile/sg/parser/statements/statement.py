"""Base class for all statements supported in sensor graph files."""

from collections import namedtuple

LocationInfo = namedtuple("LocationInfo", ['line', 'line_no', 'column'])


class SensorGraphStatement(object):
    """The base class for an AST of statements in a sensor graph file.

    Args:
        children (list(SensorGraphStatement)): A list of children statements
            to this node (optional and initialized to [] if not passed)
        location (LocationInfo): A namedtuple with information on the line this
            statement was generated from so that we can log appropriate error
            messages.
    """

    def __init__(self, children=None, location=None):
        if children is None:
            children = []

        self.children = children
        self.location = location

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

        self.execute_before(sensor_graph, scope_stack)

        for child in self.children:
            child.execute(sensor_graph, scope_stack)

        self.execute_after(sensor_graph, scope_stack)

    def execute_before(self, sensor_graph, scope_stack):
        """Execute statement before children are executed.

        Args:
            sensor_graph (SensorGraph): The sensor graph that we are building or
                modifying
            scope_stack (list(Scope)): A stack of nested scopes that may influence
                how this statement allocates clocks or other stream resources.
        """

        pass

    def execute_after(self, sensor_graph, scope_stack):
        """Execute statement after children are executed.

        Args:
            sensor_graph (SensorGraph): The sensor graph that we are building or
                modifying
            scope_stack (list(Scope)): A stack of nested scopes that may influence
                how this statement allocates clocks or other stream resources.
        """

        pass
