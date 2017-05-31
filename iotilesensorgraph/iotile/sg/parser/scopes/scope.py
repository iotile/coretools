"""Scopes provide the vessel for storing key state data during code generation."""

from builtins import str
from iotile.sg.exceptions import UnresolvedIdentifierError


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
            are operating on.
        parent (Scope): Our parent scope if we have one
            so that we can forward on requests for
            information if needed.
    """

    def __init__(self, name, sensor_graph, parent):
        self.sensor_graph = sensor_graph
        self.parent = parent
        self.name = name
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
