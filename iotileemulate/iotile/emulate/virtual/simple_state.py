"""Helper class for automatically dumping and restoring all member variables."""

import inspect
from iotile.core.exceptions import ArgumentError, DataError


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
        self._ignored_properties = set()

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

    def mark_ignored(self, name):
        """Make a property that should not be serialized/deserialized.

        Args:
            name (str): The name of the property to ignore.
        """

        self._ignored_properties.add(name)

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

    def mark_typed_list(self, name, type_object):
        """Mark a property as containing serializable objects of a given type.

        This convenience method allows you to avoid having to call
        ``mark_complex()`` whenever you need to serialize a list of objects.
        This method requires that all members of the given list be of a single
        class that contains a dump() method and a Restore() class method where
        type_object.Restore(x.dump()) == x.

        Args:
            name (str): The name of the complex property.
            type_object: The class object that will be contained inside
                this list.
        """

        if not hasattr(type_object, 'dump'):
            raise ArgumentError("The passed type object %s is missing required method: dump()" % type_object)
        if not hasattr(type_object, 'Restore'):
            raise ArgumentError("The passed type object %s is missing required method: Restore()" % type_object)

        def _dump_list(obj):
            if obj is None:
                return None

            if not isinstance(obj, list):
                raise DataError("Property %s marked as list was not a list: %s" % (name, repr(obj)))

            return [x.dump() for x in obj]

        def _restore_list(obj):
            if obj is None:
                return obj

            return [type_object.Restore(x) for x in obj]

        self.mark_complex(name, _dump_list, _restore_list)

    def mark_typed_map(self, name, type_object):
        """Mark a property as containing a map str to serializable object.

        This convenience method allows you to avoid having to call
        ``mark_complex()`` whenever you need to serialize a dict of objects.
        This method requires that all members of the given dict be of a single
        class that contains a dump() method and a Restore() class method where
        type_object.Restore(x.dump()) == x.

        Args:
            name (str): The name of the complex property.
            type_object: The class object that will be contained inside
                this dict.
        """

        if not hasattr(type_object, 'dump'):
            raise ArgumentError("The passed type object %s is missing required method: dump()" % type_object)
        if not hasattr(type_object, 'Restore'):
            raise ArgumentError("The passed type object %s is missing required method: Restore()" % type_object)

        def _dump_map(obj):
            if obj is None:
                return None

            if not isinstance(obj, dict):
                raise DataError("Property %s marked as list was not a dict: %s" % (name, repr(obj)))

            return {key: val.dump() for key, val in obj.items()}

        def _restore_map(obj):
            if obj is None:
                return obj

            return {key: type_object.Restore(val) for key, val in obj.items()}

        self.mark_complex(name, _dump_map, _restore_map)

    def mark_typed_object(self, name, type_object):
        """Mark a property as containing a serializable object.

        This convenience method allows you to avoid having to call
        ``mark_complex()`` whenever you need to serialize a complex object.
        This method requires that property ``name`` be a single class that
        contains a dump() method and a Restore() class method where
        type_object.Restore(x.dump()) == x.

        Args:
            name (str): The name of the complex property.
            type_object: The class object that will be contained inside
                this property.
        """

        if not hasattr(type_object, 'dump'):
            raise ArgumentError("The passed type object %s is missing required method: dump()" % type_object)
        if not hasattr(type_object, 'Restore'):
            raise ArgumentError("The passed type object %s is missing required method: Restore()" % type_object)

        def _dump_obj(obj):
            if obj is None:
                return None

            return obj.dump()

        def _restore_obj(obj):
            if obj is None:
                return obj

            return type_object.Restore(obj)

        self.mark_complex(name, _dump_obj, _restore_obj)

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
        return [x[0] for x in names if not x[0].startswith("_") and x[0] not in self._ignored_properties]
