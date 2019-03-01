"""Optional base class for all shared resources used in recipe steps.

A shared resource is something that should persist between single step
actions.  They are useful primarily for not repeating setup operations
that could be time consuming multiple times in a single recipe.

For example, you could setup a shared hardware_manager resource that
exits for the life of your recipe and call many steps that individually
use that hardware_manager to perform actions on an IOTile device.
"""

class SharedResource:
    """Base class for all shared resources."""

    def __init__(self):
        self.opened = False

    def open(self):
        """Open or create this resource.

        This function should be overloaded in subclasses to provide
        the actual implementation needed to open the resource.
        """

        raise NotImplementedError()

    def close(self):
        """Close or destry this resource.

        This function should be overloaded in subclasses to provide
        the actual implementation needed to open the resource.
        """

        raise NotImplementedError()
