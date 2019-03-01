"""Helper routine for finding data files bundled with iotile-build.

This module implements similar functionality to
pkg_resources.resource_filename but does it without the overhead of
pkg_resources, in particular, the very high module import time.

There are two key differences in the implementation:

1. `pkg_resources` will automatically unzip files if the wheel is
   installed in a compressed format.  This module does not.
2. `pkg_resources` lets you specify a distribution by name.  This
   module just lets you find files relative to the current package.

Both of these restrictions are parts of pkg_resources that we don't use
anyway, which is why this simpler method was implemented.
"""

import os
from iotile.core.exceptions import ArgumentError, DataError


def resource_path(relative_path=None, expect=None):
    """Return the absolute path to a resource in iotile-build.

    This method finds the path to the `config` folder inside
    iotile-build, appends `relative_path` to it and then
    checks to make sure the desired file or directory exists.

    You can specify expect=(None, 'file', or 'folder') for
    what you expect to find at the given path.

    Args:
        relative_path (str): The relative_path from the config
            folder to the resource in question.  This path can
            be specified using / characters on all operating
            systems since it will be normalized before usage.
            If None is passed, the based config folder will
            be returned.
        expect (str): What the path should resolve to, which is
            checked before returning, raising a DataError if
            the check fails.  You can pass None for no checking,
            file for checking `os.path.isfile`, or folder for
            checking `os.path.isdir`.  Default: None

    Returns:
        str: The normalized absolute path to the resource.
    """

    if expect not in (None, 'file', 'folder'):
        raise ArgumentError("Invalid expect parameter, must be None, 'file' or 'folder'",
                            expect=expect)

    this_dir = os.path.dirname(__file__)
    _resource_path = os.path.join(this_dir, '..', 'config')

    if relative_path is not None:
        path = os.path.normpath(relative_path)
        _resource_path = os.path.join(_resource_path, path)

    if expect == 'file' and not os.path.isfile(_resource_path):
        raise DataError("Expected resource %s to be a file and it wasn't" % _resource_path)
    elif expect == 'folder' and not os.path.isdir(_resource_path):
        raise DataError("Expected resource %s to be a folder and it wasn't" % _resource_path)

    return os.path.abspath(_resource_path)
