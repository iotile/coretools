from setuptools import setup, find_packages

import version

setup(
    name="iotile-transport-native-ble",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    install_requires=[
        "iotile-core>=5.0.0,<6",
        "bable-interface>=1.2.0,<2"
    ],
    python_requires=">=3.5,<4",
    entry_points={'iotile.device_adapter': ['ble = iotile_transport_native_ble.device_adapter:NativeBLEDeviceAdapter'],
                  'iotile.virtual_interface': ['ble = iotile_transport_native_ble.virtual_ble:NativeBLEVirtualInterface'],
                  'iotile.config_variables': ['ble = iotile_transport_native_ble.config_variables:get_variables']},
    description="IOTile Native BLE Transport Plugin",
    author="Arch",
    author_email="info@arch-iot.com",
    url="https://github.com/iotile/coretools",
    keywords=["iotile", "arch", "embedded", "hardware", "firmware", "ble", "bluetooth"],
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: Unix",  # FIXME: change as soon as bable-interface will be deployed on Windows and Mac
        "Topic :: Software Development :: Libraries :: Python Modules"
    ],
    long_description="""\
IOTile Native BLE Transport Plugin
----------------------------------

A python plugin for the IOTile framework that allows communication with IOTile devices over
Bluetooth Smart using the native Bluetooth controller, embedded in your computer.  See https://www.arch-iot.com.
"""
)
