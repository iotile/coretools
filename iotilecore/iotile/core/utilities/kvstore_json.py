# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

import json
import os.path
import sys
import os
import platform
from iotile.core.utilities.paths import settings_directory

class JSONKVStore(object):
    """A Key Value store based on flat json files with atomic write semantics

    This is intended as a drop in replacement for SQLiteKVStore.  Note that the
    implementation is not meant to be efficient in the sense of caching the file
    in memory.  Instead it has read-through and write-through semantics where the
    file is reloaded every time a request is made.

    Args:
        name (string): The name of the file to use as a persistent store for this KVStore
        folder (string): Optional folder to store the file.  If None, the system default
            settings directory is used
        respect_venv (bool): Make folder relative to the current virtual environment if there
            is one.
    """

    DefaultFolder = settings_directory()

    def __init__(self, name, folder=None, respect_venv=False):
        if folder is None:
            folder = JSONKVStore.DefaultFolder

        #If we are relative to a virtual environment, place the registry into that virtual env
        #Support both virtualenv and pythnon 3 venv
        if respect_venv and hasattr(sys, 'real_prefix'):
            folder = sys.prefix
        elif respect_venv and hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix:
            folder = sys.prefix

        if not os.path.exists(folder):
            os.makedirs(folder, 0o755)

        jsonfile = os.path.join(folder, name)

        self.file = jsonfile

    def _load_file(self):
        """Load all entries from json backing file
        """

        if not os.path.exists(self.file):
            return {}

        with open(self.file, "r") as infile:
            data = json.load(infile)

        return data

    def _save_file(self, data):
        """Attempt to atomically save file by saving and then moving into position

        The goal is to make it difficult for a crash to corrupt our data file since
        the move operation can be made atomic if needed on mission critical filesystems.
        """

        if platform.system() == 'Windows':
            with open(self.file, "w") as outfile:
                json.dump(data, outfile)
        else:
            newpath = self.file + '.new'

            with open(newpath, "w") as outfile:
                json.dump(data, outfile)

            os.rename(
                os.path.realpath(newpath),
                os.path.realpath(self.file)
            )

    def get(self, key):
        """Get a value by its key

        Args:
            key (string): The key used to store this value

        Returns:
            value (string): The value associated to the key

        Raises:
            KeyError: if the key was not found
        """

        data = self._load_file()
        return data[key]

    def get_all(self):
        """Return a list of all (key, value) tuples in the kv store

        Returns:
            list(string, string): A list of key, value pairs
        """

        data = self._load_file()
        return data.items()

    def remove(self, key):
        """Remove a key from the data store

        Args:
            key (string): The key to remove

        Raises:
            KeyError: if the key was not found
        """

        data = self._load_file()
        del data[key]
        self._save_file(data)

    def try_get(self, key):
        """Try to get a value by its key, returning None if not found

        Args:
            key (string): The key used to store this value

        Returns:
            value (string): The value associated to the key or None
        """

        data = self._load_file()
        return data.get(key, None)

    def set(self, key, value):
        """Set the value of a key

        Args:
            key (string): The key used to store this value
            value (string): The value to store
        """

        data = self._load_file()
        data[key] = value
        self._save_file(data)

    def clear(self):
        """Clear all values from this kv store
        """

        self._save_file({})
