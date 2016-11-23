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

def parse_version():
    VERSIONFILE = "iotilecore/__version__.py"
    verstrline = open(VERSIONFILE, "rt").read()
    VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
    mo = re.search(VSRE, verstrline, re.M)
    if mo:
        return mo.group(1)
    else:
        raise RuntimeError("Unable to find version string in %s." % (VERSIONFILE,))

setup(
    name="iotilecore",
    packages=find_packages(),
    version=parse_version(),
    license="LGPLv3",
    install_requires=[
        "beautifulsoup4==4.3.2",
        "Cheetah==2.4.4",
        "decorator==3.4.0",
        "Markdown==2.5.2",
        "nose==1.3.4",
        "pycparser==2.10",
        "pyparsing==2.0.3",
        "pyserial>=2.7",
        "pytest==2.6.4",
        "six>=1.9.0",
        "xlsxwriter>=0.6.7",
        "crcmod>=1.7.0",
        "pint>=0.6.0"
    ],
    entry_points={
        'console_scripts': [
            'iotile = iotile.core.scripts.iotile:main',
        ]
    },
    description="IOTile Core Tools",
    author="Arch",
    author_email="info@arch-iot.com",
    url="http://github.com/iotile/py_iotilecore",
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

A python library for interacting with IOTile based devices.  See https://www.arch-iot.com.

"""
)
