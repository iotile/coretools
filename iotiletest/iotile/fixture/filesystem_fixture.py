"""A Mock class for overriding open calls."""

import pytest

from contextlib import contextmanager
from io import StringIO


class MockFileOpen:
    def __init__(self):
        """Constructor."""

        self.files = {}
        self._real_open = open

    @contextmanager
    def mock_open(self, filename, params):
        """Mock open a file."""

        if filename not in self.files:
            with self._real_open(filename, params) as realfile:
                yield realfile
        else:
            if params[0] == 'r':
                self.files[filename].seek(0)
            elif params[0] == 'w':
                self.files[filename] = StringIO()

            yield self.files[filename]

    def add_file(self, path, contents=""):
        """Add a mock file with the given contents.

        Args:
            path (string): The path to the fake file
            contents (string): Optional file contents
        """

        self.files[path] = StringIO(contents)

    def from_file(self, path, content_path):
        """Add a mock file from the actual file.

        Args:
            path (string): The path to the fake file
            content_path (string): The actual file path
        """

        with self._real_open(content_path, "rb") as f:
            contents = f.read()

        self.add_file(path, contents)


@pytest.fixture
def mock_fs():
    """Create a mock fs object that can be used to patch file opens."""

    mock = MockFileOpen()
    return mock
