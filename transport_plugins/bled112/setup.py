from setuptools import setup, find_packages
import version

setup(
    name="iotile-transport-bled112",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    install_requires=[
        "iotile-core>=5.0.0,<6",
        "pyserial>=3.4.0,<4"
    ],
    python_requires=">=3.5,<4",
    entry_points={'iotile.device_adapter': ['bled112 = iotile_transport_bled112.bled112:BLED112Adapter'],
                  'iotile.device_server': ['bled112 = iotile_transport_bled112.server_bled112:BLED112Server'],
                  'iotile.config_variables': ['bled112 = iotile_transport_bled112.config_variables:get_variables']},
    description="IOTile BLED112 Transport Plugin",
    author="Arch",
    author_email="info@arch-iot.com",
    url="http://github.com/iotile/coretools",
    keywords=["iotile", "arch", "embedded", "hardware", "firmware"],
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Software Development :: Libraries :: Python Modules"
        ],
    long_description="""\
IOTile BLED112 Transport Plugin
-------------------------------

A python plugin for the IOTile framework that allows communication with IOTile devices over
Bluetooth Smart using the BLED112 dongle.  See https://www.arch-iot.com.
"""
)
