from .scope import Scope


class RootScope(Scope):
    """The global scope that contains all others.

    Args:
        sensor_graph (SensorGraph): The SensorGraph we
            are operating on.
        parent (Scope): Our parent scope if we have one
            so that we can forward on requests for
            information if needed
    """


