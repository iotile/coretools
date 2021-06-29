from setuptools import setup, find_packages

import version

setup(
    name="iotile-transport-websocket",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    install_requires=[
        "iotile-core>=5.2",
        "msgpack>=1",
        "websockets>=9.1",
        "iotile-transport-socket-lib>=1.1",
    ],
    python_requires=">=3.7,<4",
    entry_points={
        'iotile.device_adapter': [
            'ws = iotile_transport_websocket:WebSocketDeviceAdapter'
        ],
        'iotile.device_server': [
            'websockets = iotile_transport_websocket:WebSocketDeviceServer'
        ]
    },
    description="IOTile Websocket Transport Plugin",
    author="Arch",
    author_email="info@arch-iot.com",
    url="http://github.com/iotile/coretools",
    keywords=["iotile", "arch", "embedded", "hardware", "firmware"],
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules"
        ],
    long_description="""\
IOTile Websocket Transport Plugin
---------------------------------

A python plug for IOTile CoreTools that allows interacting with IOTile devices through
websockets, including providing DeviceAdapters that allow controlling devices.
"""
)
