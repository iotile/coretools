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

from setuptools import setup, find_packages

import os
from os.path import basename

import re
def parse_version():
    VERSIONFILE="iotilecore/__version__.py"
    verstrline = open(VERSIONFILE, "rt").read()
    VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
    mo = re.search(VSRE, verstrline, re.M)
    if mo:
        return mo.group(1)
    else:
        raise RuntimeError("Unable to find version string in %s." % (VERSIONFILE,))

def list_data_files():
    result = [ ]
    dirname = os.path.join(os.path.dirname(__file__), 'iotilecore')
    print dirname
    for root, dirs, files in os.walk(os.path.join(dirname, 'config')):
        for filename in files:
            result.append( os.path.join( root, filename )[len(dirname)+1:] )
    return result

setup(
    name = "iotilecore",
    packages = find_packages(),
    version = parse_version(),
    license = "LGPLv3",
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
        "six==1.9.0",
        "xlsxwriter>=0.6.7",
        "interval>=1.0.0",
        "crcmod>=1.7.0",
        "pint>=0.6.0"
    ],
    package_data={ #This could be better
        'iotilecore': list_data_files()
    },
    entry_points={
        'console_scripts': [
            'iotile = iotilecore.scripts.iotile:main',
        ]
    },
    description = "IOTile Core ",
    author = "Arch",
    author_email = "info@arch-iot.com",
    url = "http://github.com/iotile/lib_iotilecore",
    keywords = ["iotile", "arch", "embedded", "hardware"],
    classifiers = [
        "Programming Language :: Python",
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules"
        ],
    long_description = """\
IOTileCore
------

A python library for interacting with IOTile based devices.  See https://www.arch-iot.com.

"""
)