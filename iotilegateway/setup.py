# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

# Caveats and possible issues
# Mac OS X
# - when using a virtualenv, readline is not properly installed into the virtualenv
#   and cannot be imported.  You need to install it using easy_install as described here
#   http://calvinx.com/tag/readline/

from setuptools import setup, find_packages
import version

setup(
    name="iotile-gateway",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    install_requires=[
        "tornado>=4.4.0,<=5.0.0",
        "iotile-core>=3.0.1",
        "monotonic",
        "msgpack-python>=0.4.8",
        "ws4py>=0.3.5"
    ],
    entry_points={
        'console_scripts': [
            'iotile-gateway = iotilegateway.main:main',
            'iotile-supervisor = iotilegateway.supervisor.main:main',
            'iotile-send-rpc = iotilegateway.supervisor.send_rpc:main'
        ],
        'iotile.gateway_agent': [
            'websockets = iotilegateway.ws_agent:WebSocketGatewayAgent'
        ],
        'iotile.virtual_tile': [
            'service_delegate = iotilegateway.supervisor.service_tile:ServiceDelegateTile'
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
IOTileGateway
-------------

A python package providing basic gateway infrastructure for talking to multiple IOTile devices.

See https://www.arch-iot.com.

"""
)
