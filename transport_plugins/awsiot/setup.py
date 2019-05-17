from setuptools import setup, find_packages

import version

setup(
    name="iotile-transport-awsiot",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    install_requires=[
        "iotile-core>=5.0.0,<6",
        "AWSIoTPythonSDK>=1.4.3,<2"
    ],
    python_requires=">=3.5,<4",
    entry_points={'iotile.device_adapter': ['awsiot = iotile_transport_awsiot.device_adapter:AWSIOTDeviceAdapter'],
                  'iotile.virtual_interface': ['awsiot = iotile_transport_awsiot.virtual_interface:AWSIOTVirtualInterface'],
                  'iotile.gateway_agent': ['awsiot = iotile_transport_awsiot.gateway_agent:AWSIOTGatewayAgent']},
    description="IOTile AWS IOT Transport Plugin",
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
IOTile AWS IOT Transport Plugin
-------------------------------

A python plug for IOTile CoreTools that allows interacting with IOTile devices through
AWS IOT, including providing virtual agents that act as devices and DeviceAdapters
that allow controlling devices.
"""
)
