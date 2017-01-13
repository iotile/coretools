# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International 
# are copyright Arch Systems Inc.

#Caveats and possible issues
#Mac OS X
# - when using a virtualenv, readline is not properly installed into the virtualenv
#   and cannot be imported.  You need to install it using easy_install as described here
#   http://calvinx.com/tag/readline/

import re

from setuptools import setup, find_packages
import version

setup(
    name="iotile-test",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    install_requires=[
        "iotile-core>=3.0.0"
    ],
    description="IOTile Test Infrastructure",
    entry_points={'iotile.virtual_device': ['simple = iotile.mock.devices.simple_virtual_device:SimpleVirtualDevice',
                                            'report_test = iotile.mock.devices.report_test_device:ReportTestDevice'],
                  'iotile.proxy': ['simple = iotile.mock.devices.simple_virtual_proxy']},
    author="Arch",
    author_email="info@arch-iot.com",
    url="https://github.com/iotile/coretools/iotilecore",
    keywords=["iotile", "arch", "embedded", "hardware"],
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules"
        ],
    long_description="""\
IOTileTest
----------

A python package for testing IOTile based infrastructure including mocks for major portions.  

See https://www.arch-iot.com.
"""
)
