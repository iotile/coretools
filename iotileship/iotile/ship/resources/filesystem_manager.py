''' A Resource for operating on a Filesystem

    Can work on either a directory or a unmounted block device

    Important: mounting and unmounting of a block device requires the udisksctl utility, which is included with
    most distributions of Ubuntu

    All Steps using this Resource will use self.root as the root directory to find other files

    Root directory is a pathlib.Path

'''

import subprocess
import pathlib
import sys

from iotile.core.utilities.schema_verify import DictionaryVerifier
from iotile.core.utilities.schema_verify import StringVerifier
from iotile.core.exceptions import ArgumentError
from .shared_resource import SharedResource

RESOURCE_ARG_SCHEMA = DictionaryVerifier(desc="filesystem_manager arguments")
RESOURCE_ARG_SCHEMA.add_required("res_path", StringVerifier("path to resource to work with. "
                                                            "Specify file:// for a directory or block:// for an unmounted disk partition"))


class FilesystemManagerResource(SharedResource):
    '''
    Arguments:
        path (str): Required. One of:
            file://<path> : Path to a directory that will be worked on
            block://<path> : Path to a block device to work on (typically /dev/sd...)
    '''


    ARG_SCHEMA = RESOURCE_ARG_SCHEMA
    _allowed_types = ["file", "block"]

    def __init__(self, args):
        super(FilesystemManagerResource, self).__init__()

        self._path = args.get('res_path')

        if not "://" in self._path:
            raise ArgumentError("Cannot detect resource type (looking for something like 'file://)'",
                                parameter_name="res_path")

        self._type = self._path.split('://')[0]
        self._resource_loc = self._path.split('://')[1]

        if self._type not in self._allowed_types:
            raise ArgumentError("FilesystemManagerResource unknown filesystem type", parameter_name="res_path")

        if self._type == "block" and sys.platform != "linux":
            raise ArgumentError("block;// paths are only supported on Linux. \
                Mount the device and pass the filepath", parameter_name="res_path")

        if self._type == "block" and sys.platform == "linux":
            try:
                subprocess.run(['udisksctl', 'help'], stdout=subprocess.DEVNULL, check=True)
            except subprocess.CalledProcessError:
                print("Could not find 'udisksctl'. Make sure it's installed")
                raise

        self.root = None
        self._unmount_in_close = False

    #If self._resource_loc is mounted, returns pathlib.Path to mount location
    #If not, returns None
    def _get_mountpoint(self):
        info_cmd = ['udisksctl', 'info', '--block-device', self._resource_loc]
        info_proc = subprocess.run(info_cmd, stdout=subprocess.PIPE, check=True, universal_newlines=True)

        for line in info_proc.stdout.splitlines():
            if "MountPoints:" in line:
                split = line.split()
                if len(split) > 1:
                    return pathlib.Path(split[1])
                return None

        raise RuntimeError("udisksctl failed to report MountPoints")


    def open(self):
        if self._type == "block":

            if not pathlib.Path(self._resource_loc).exists:
                raise FileNotFoundError("FilesystemManagerResource path not found")

            #Check if we're already mounted
            self.root = self._get_mountpoint()
            if self.root is None:
                #Mount
                mount_cmd = ['udisksctl', 'mount', '--block-device', self._resource_loc, '--no-user-interaction']
                subprocess.run(mount_cmd, check=True, universal_newlines=True)

                self.root = self._get_mountpoint()
                self._unmount_in_close = True

            #Sanity check
            if not self.root.exists():
                raise RuntimeError("Couldn't find mount location")

        elif self._type == "file":
            self.root = pathlib.Path(self._resource_loc)

            if not self.root.exists():
                raise FileNotFoundError("FilesystemManagerResource path not found")

        self.opened = True


    def close(self):
        if self._type == "block" and self._unmount_in_close:
            unmount_cmd = ['udisksctl', 'unmount', '--block-device', self._resource_loc,
                           '--no-user-interaction']
            subprocess.run(unmount_cmd, check=True, universal_newlines=True)

        self.opened = False
