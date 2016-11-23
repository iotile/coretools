# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.


import os.path
import os
import platform

def settings_directory():
    """
    Find a per user settings directory that is appropriate for each
    type of system that we are installed on.
    """

    system = platform.system()

    basedir = None

    if system == 'Windows':
        if 'APPDATA' in os.environ:
            basedir = os.environ['APPDATA']
    elif system == 'Darwin':
        basedir = os.path.expanduser('~/Library/Preferences')

    #If we're not on Windows or Mac OS X, assume we're on some
    #kind of posix system where the appropriate place would be
    #~/.config
    if basedir is None:
        basedir = os.path.expanduser('~')
        basedir = os.path.join(basedir, '.config')

    settings_dir = os.path.abspath(os.path.join(basedir, 'IOTile-Core'))
    if not os.path.exists(settings_dir):
        os.makedirs(settings_dir, 0755)

    return settings_dir
