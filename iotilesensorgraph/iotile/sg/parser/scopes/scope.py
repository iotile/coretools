"""Scopes provide the vessel for storing key state data during code generation."""

from builtins import str
from iotile.sg.exceptions import UnresolvedIdentifierError, SensorGraphSemanticError


class Scope(object):
    """An environment used during code generation.

    Scopes contain all of the state information used
    to assign triggers to nodes and link them into a
    SensorGraph during the code generation process.

    They have four main entry points.  In what follows,
    NodeInput refers to a tuple of StreamIdentifier and
    InputTrigger that can be used to connect a node to
    a Streamwalker with a trigger.

    - trigger_chain(): Allocate a NodeInput that will
      trigger a node when the previous node in this
      chain is finished.
    - clock(interval): Allocate a NodeInput that will
      trigger every interval seconds.
    - resolve_event(event_name): Resolve an event_name
      to a NodeInput.
    - resolve_identifier(identifier_name): Resolve an
      identifier to an object

    Args:
        name (str): An identifier for this scope to be
            used in debug messages
        sensor_graph (SensorGraph): The SensorGraph we
            are operating on
        allocator (StreamAllocator): The global stream
            allocator we are using
        parent (Scope): Our parent scope if we have one
            so that we can forward on requests for
            information if needed.
    """

    def __init__(self, name, sensor_graph, allocator, parent):
        self.sensor_graph = sensor_graph
        self.parent = parent
        self.name = name
        self.allocator = allocator
        self._known_identifiers = {}

    def add_identifier(self, name, obj):
        """Add a known identifier resolution.

        Args:
            name (str): The name of the identifier
            obj (object): The object that is should resolve to
        """

        name = str(name)
        self._known_identifiers[name] = obj

    def resolve_identifier(self, name, expected_type=None):
        """Resolve an identifier to an object.

        There is a single namespace for identifiers so the user also should
        pass an expected type that will be checked against what the identifier
        actually resolves to so that there are no surprises.

        Args:
            name (str): The name that we want to resolve
            expected_type (type): The type of object that we expect to receive.
                This is an optional parameter.  If None is passed, no type checking
                is performed.

        Returns:
            object: The resolved object
        """

        name = str(name)

        if name in self._known_identifiers:
            obj = self._known_identifiers[name]
            if expected_type is not None and not isinstance(obj, expected_type):
                raise UnresolvedIdentifierError(u"Identifier resolved to an object of an unexpected type", name=name, expected_type=expected_type.__name__, resolved_type=obj.__class__.__name__)

            return obj

        if self.parent is not None:
            try:
                return self.parent.resolve_identifier(name)
            except UnresolvedIdentifierError:
                pass

        raise UnresolvedIdentifierError(u"Could not resolve identifier", name=name, scope=self.name)

    def trigger_chain(self):
        """Return a NodeInput tuple for creating a node.

        Returns:
            (StreamIdentifier, InputTrigger)
        """

        raise SensorGraphSemanticError("There is no trigger chain in this scope since no triggering criteria have been set", scope=self.name)

    def clock(self, interval, basis):
        """Return a NodeInput tuple for triggering an event every interval.

        Args:
            interval (int): The interval (in seconds) at which this input should
                trigger.
            basis (str): The basis to use for calculating the interval.  This
                can either be system, tick_1 or tick_2.  System means that the
                clock will use either the fast or regular builtin tick.  Passing
                tick_1 or tick_2 will cause the clock to be generated based on
                the selected tick.
        """

        raise SensorGraphSemanticError("There is not default clock defined in this scope", scope=self.name)
