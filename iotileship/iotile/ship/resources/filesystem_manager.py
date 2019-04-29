import pathlib

from iotile.core.utilities.schema_verify import DictionaryVerifier
from iotile.core.utilities.schema_verify import StringVerifier
from .shared_resource import SharedResource

RESOURCE_ARG_SCHEMA = DictionaryVerifier(desc="filesystem_manager arguments")
RESOURCE_ARG_SCHEMA.add_required("path", StringVerifier("path to filesystem to work with"))


class FilesystemManagerResource(SharedResource):
    """ A Resource for operating on a Filesystem

    All Steps using this Resource will use self.root as the root directory to find other files

    Root directory is a pathlib.Path

    Arguments:
        path (str): Path to filesystem to work with
    """

    ARG_SCHEMA = RESOURCE_ARG_SCHEMA
    _allowed_types = ["file", "block"]

    def __init__(self, args):
        super(FilesystemManagerResource, self).__init__()

        self._path = args.get('path')
        self.root = None

    def open(self):
        if not pathlib.Path(self._path).exists():
            raise FileNotFoundError("FilesystemManagerResource path not found")

        self.root = pathlib.Path(self._path)
        self.opened = True

    def close(self):
        self.opened = False
