from setuptools import setup, find_packages

import os
from os.path import basename

def list_data_files():
    result = [ ]
    dirname = os.path.join(os.path.dirname(__file__), 'pymomo')
    print dirname
    for root, dirs, files in os.walk(os.path.join(dirname, 'config')):
        for filename in files:
            result.append( os.path.join( root, filename )[len(dirname)+1:] )
    return result

setup(
    name = "pymomo",
    packages = find_packages(),
    version = "1.0.4",
    install_requires=[
        "beautifulsoup4==4.3.2",
        "BTrees==4.1.1",
        "Cheetah==2.4.4",
        "cmdln==1.1.2",
        "colorama==0.3.3",
        "decorator==3.4.0",
        "dirspec==13.10",
        "intelhex==1.5",
        "Markdown==2.5.2",
        "nose==1.3.4",
        "persistent==4.0.8",
        "py==1.4.26",
        "pycparser==2.10",
        "pyparsing==2.0.3",
        "pyserial==2.7",
        "pytest==2.6.4",
        "six==1.9.0",
        "transaction==1.4.3",
        "zc.lockfile==1.1.0",
        "ZConfig==3.0.4",
        "zdaemon==4.0.1",
        "ZEO==4.1.0",
        "ZODB==4.1.0",
        "ZODB3==3.11.0",
        "zope.interface==4.1.2"
    ],
    package_data={ #This could be better
        'pymomo': list_data_files()
    },
    entry_points={
        'console_scripts': [
            'momo = pymomo.scripts.momo:main',
            'momo-mod = pymomo.scripts.modtool:main',
            'momo-gsm = pymomo.scripts.gsmtool:main',
            'momo-pcb = pymomo.scripts.pcbtool:main',
            'momo-hex = pymomo.scripts.hextool:main',
            'momo-mib = pymomo.scripts.mibtool:main',
            'momo-reportinator = pymomo.scripts.reportinator:main',
            'momo-picunit = pymomo.scripts.picunit:main',
            'momo-multisensor = pymomo.scripts.multisensor:main',
            'momo-sensor = pymomo.scripts.momosensor:main'
        ]
    },
    description = "WellDone Mobile Monitor (MoMo) Interaction Library",
    author = "WellDone International",
    author_email = "info@welldone.org",
    url = "http://github.com/welldone/pymomo",
    keywords = ["momo", "remote", "monitoring", "embedded", "hardware"],
    classifiers = [
        "Programming Language :: Python",
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules"
        ],
    long_description = """\
PyMoMo
------

A python library for interacting with MoMo devices.  See https://momo.welldone.org.

"""
)