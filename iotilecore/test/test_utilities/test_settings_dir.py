# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

import unittest
import os.path
import os
import platform
from iotile.core.exceptions import *
from iotile.core.utilities.paths import settings_directory

class TestSettingsDirectory(unittest.TestCase):
    def setUp(self):
        self.settings_dir = settings_directory()
        self.confdir = os.path.join(os.path.expanduser('~'), '.config')

    def test_settings_dir(self):
        assert os.path.exists(self.settings_dir)

    @unittest.skipIf(platform.system() != 'Linux', 'Linux specific test')
    def test_settings_linix(self):
        settings_dir = os.path.abspath(os.path.join(self.confdir, 'IOTile-Core'))

        assert settings_dir == self.settings_dir

    @unittest.skipIf(platform.system() != 'Windows', 'Windows specific test')
    def test_settings_windows(self):
        if 'APPDATA' in os.environ:
            base = os.environ['APPDATA']
        else:
            base = self.confdir

        settings_dir = os.path.abspath(os.path.join(base, 'IOTile-Core'))
        assert settings_dir == self.settings_dir

    @unittest.skipIf(platform.system() != 'Darwin', 'Mac OS X specific test')
    def test_settings_darwin(self):

        settings_dir = os.path.abspath(os.path.join(os.path.expanduser('~'), 'Library', 'Preferences',
                                                            'IOTile-Core'))

        assert settings_dir == self.settings_dir
