"""Setup file for iotile-transport-jlink package."""

from setuptools import setup, find_packages
import version

setup(
    name="iotile-transport-jlink",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    install_requires=[
        "iotile-core>=4.0.0",
        "pylink-square>=0.1.3",
        "pylibftdi>=0.17.0"
    ],
    python_requires=">=3.5,<4",
    entry_points={'iotile.device_adapter': ['jlink = iotile_transport_jlink.jlink:JLinkAdapter']},
    description="IOTile JLINK Transport Plugin",
    author="Arch",
    author_email="info@arch-iot.com",
    url="http://github.com/iotile/coretools",
    keywords=["iotile", "arch", "embedded", "hardware", "firmware"],
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 2 - Pre-Alpha",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Software Development :: Libraries :: Python Modules"
        ],
    long_description="""\
IOTile JLink Transport Plugin
-------------------------------

A python plugin into IOTile Coretools that allows for using a JLink adapter to
send RPCs over an IOTile module's SWD interface.  The IOTile device needs to be
compiled with support for the SWD RPC interface for this to work.
"""
)
