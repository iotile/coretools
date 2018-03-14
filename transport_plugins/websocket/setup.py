from setuptools import setup, find_packages

import version
# FIXME: use 'ws' instead of 'ws2'

setup(
    name="iotile-transport-websocket",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    install_requires=[
        "iotile-core>=3.20.2"
    ],

    entry_points={
        'iotile.device_adapter': [
            'ws2 = iotile_transport_websocket.device_adapter:WebSocketDeviceAdapter'
        ]
    },
    description="IOTile Websocket Transport Plugin",
    author="Arch",
    author_email="info@arch-iot.com",
    url="http://github.com/iotile/coretools",
    keywords=["iotile", "arch", "embedded", "hardware", "firmware"],
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules"
        ],
    long_description="""\
IOTile Websocket Transport Plugin
------

A python plug for IOTile CoreTools that allows interacting with IOTile devices through
websockets, including providing DeviceAdapters that allow controlling devices.
"""
)
