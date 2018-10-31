"""Helper class for automatically dumping and restoring all member variables."""

import inspect
from iotile.core.exceptions import ArgumentError


class SerializableState(object):
    """A helper class that can dump itself to a dictionary.

    This class only dumps and restores public data members that it discovers
    using the inspect module.  If the datatype of the public member is such
    that it needs preprocessing before being json serializable, you can pass
    its name to mark_complex(name, serializer, deserializer) and those functions
    will be called on dump and restore to serialize/deserialize the property.
    """

    def __init__(self):
        self._complex_properties = {}

    def dump(self):
        """Serialize this state by iterating over all public properties using inspect.

        Returns:
            dict: The serialized representation of this state.
        """

        return {x: self.dump_property(x) for x in self.get_properties()}

    def restore(self, state):
        """Restore this state from the output of a previous call to dump().

        Only those properties in this object and listed in state will be
        updated.  Other properties will not be modified and state may contain
        keys that do not correspond with properties in this object.

        Args:
            state (dict): A serialized representation of this object.
        """

        own_properties = set(self.get_properties())
        state_properties = set(state)

        to_restore = own_properties.intersection(state_properties)

        for name in to_restore:
            value = state.get(name)

            if name in self._complex_properties:
                value = self._complex_properties[name][1](value)

            setattr(self, name, value)

    def mark_complex(self, name, serializer, deserializer):
        """Mark a property as complex with serializer and deserializer functions.

        Args:
            name (str): The name of the complex property.
            serializer (callable): The function to call to serialize the property's
                value to something that can be saved in a json.
            deserializer (callable): The function to call to unserialize the property
                from a dict loaded by a json back to the original value.
        """

        self._complex_properties[name] = (serializer, deserializer)

    def dump_property(self, name):
        """Serialize a property of this class by name.

        Args:
            name (str): The name of the property to dump.

        Returns:
            object: The serialized value of the property.
        """

        if not hasattr(self, name):
            raise ArgumentError("Unknown property %s" % name)

        value = getattr(self, name)
        if name in self._complex_properties:
            value = self._complex_properties[name][0](value)

        return value

    def get_properties(self):
        """Get a list of all of the public data properties of this class.

        Returns:
            list of str: A list of all of the public properties in this class.
        """

        names = inspect.getmembers(self, predicate=lambda x: not inspect.ismethod(x))
        return [x[0] for x in names if not x[0].startswith("_")]
