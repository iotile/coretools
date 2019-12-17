from setuptools import setup, find_packages

import version

setup(
    name="iotile-transport-socket-lib",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    install_requires=[
        "iotile-core>=5.0.0,<6",
        "msgpack>=0.6.1,<1"
    ],
    python_requires=">=3.5,<4",
    entry_points={
        'iotile.device_adapter': [
            'unix = iotile_transport_socket_lib.unix_socket:UnixSocketDeviceAdapter',
            'tcp = iotile_transport_socket_lib.tcp_socket:TcpSocketDeviceAdapter'
        ],
        'iotile.device_server': [
            'unixsocket = iotile_transport_socket_lib.unix_socket:UnixSocketDeviceServer',
            'tcpsocket = iotile_transport_socket_lib.tcp_socket:TcpSocketDeviceServer'
        ]
    },
    description="IOTile Transport Socket Library Plugin",
    author="Arch",
    author_email="info@arch-iot.com",
    url="http://github.com/iotile/coretools",
    keywords=["iotile", "arch", "embedded", "hardware", "firmware"],
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules"
        ],
    long_description="""\
IOTile Transport Socket Library Plugin
--------------------------------------

A python plug for IOTile CoreTools that provides common message formats, packing routines and
other code that is useful for performing iotile operations via socket or 
socket-like protocols. Not particularily useful on it's own.
"""
)