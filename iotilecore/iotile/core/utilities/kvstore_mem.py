"""A simple in memory kv store for testing purposes."""

# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.


class InMemoryKVStore(object):
    """A Key Value store based on an in memory dict

    This is intended as a drop in replacement for SQLiteKVStore.  Note that this KV store
    is not persistent across multiple process invocations so it is primarily useful for
    testing, not production use.

    Args:
        name (string): The name of the file to use as a persistent store for this KVStore.  This
            is ignored for this kv store type.
        respect_venv (bool): Make folder relative to the current virtual environment if there
            is one.  This is ignored for this kv_store type
    """

    _shared_data = {}

    def __init__(self, name, respect_venv=False):
        pass

    def get(self, key):
        """Get a value by its key.

        Args:
            key (string): The key used to store this value

        Returns:
            value (string): The value associated to the key

        Raises:
            KeyError: if the key was not found
        """

        return self._shared_data[key]

    def get_all(self):
        """Return a list of all (key, value) tuples in the kv store.

        Returns:
            list(string, string): A list of key, value pairs
        """

        return self._shared_data.items()

    def remove(self, key):
        """Remove a key from the data store.

        Args:
            key (string): The key to remove

        Raises:
            KeyError: if the key was not found
        """

        del self._shared_data[key]

    def try_get(self, key):
        """Try to get a value by its key, returning None if not found.

        Args:
            key (string): The key used to store this value

        Returns:
            value (string): The value associated to the key or None
        """

        return self._shared_data.get(key, None)

    def set(self, key, value):
        """Set the value of a key.

        Args:
            key (string): The key used to store this value
            value (string): The value to store
        """

        self._shared_data[key] = value

    def clear(self):
        """Clear all values from this kv store."""

        InMemoryKVStore._shared_data = {}
