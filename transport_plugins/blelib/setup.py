from setuptools import setup, find_packages
import version

setup(
    name="iotile-transport-blelib",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    install_requires=[
        "iotile-core>=5.0.0,<6"
    ],
    python_requires=">=3.5,<4",
    description="IOTile BLE Support Package",
    author="Arch Systems",
    author_email="info@archsys.io",
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
IOTile BLE Support Library
-------------------------------

Common bluetoooth interfaces, classes and supporting modules for implementing
Bluetooth Low-Energy based DeviceAdapters that can work with a variety of
bluetooth hardware.

See https://www.arch-iot.com.
"""
)
