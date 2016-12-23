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
    name="iotile-core",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    install_requires=[
        "decorator>=3.4.0",
        "pyparsing>=2.0.3",
        "six>=1.9.0",
        "crcmod>=1.7.0",
        "ws4py>=0.3.5",
        "msgpack-python>=0.4.8",
        "python-dateutil>=2.6.0",
        "pyreadline>=2.1.0",
        "python-dateutil>=2.6.0"
    ],
    entry_points={
        'console_scripts': [
            'iotile = iotile.core.scripts.iotile_script:main',
        ],
        'iotile.cmdstream': [
            'ws = iotile.core.hw.transport.websocketstream:WebSocketStream',
            'recorded = iotile.core.hw.transport.recordedstream:RecordedStream'
        ],
        'iotile.report_format': [
            'individual = iotile.core.hw.reports.individual_format:IndividualReadingReport'
            ]
    },
    description="IOTile Core Tools",
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
IOTileCore
------

A python package for interacting with IOTile based devices.  See https://www.arch-iot.com.

"""
)
