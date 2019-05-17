"""Package setup file for iotile-emulate."""

from setuptools import setup, find_packages
import version

setup(
    name="iotile-emulate",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    description="IOTile Device Emulation",
    install_requires=[
        "iotile-core>=5.0.0,<6",
        "iotile-sensorgraph>=1,<2"
    ],
    python_requires=">=3.5,<4",
    entry_points={'iotile.virtual_device': ['reference_1_0 = iotile.emulate.demo:DemoReferenceDevice',
                                            'emulation_demo = iotile.emulate.demo:DemoEmulatedDevice'],
                  'iotile.proxy': ['emudmo = iotile.emulate.demo:DemoTileProxy'],
                  'iotile.device_adapter': ['emulated = iotile.emulate.transport:EmulatedDeviceAdapter'],
                  'iotile.emulated_tile': ['refcon_1 = iotile.emulate.reference:ReferenceController']},
    author="Arch",
    author_email="info@arch-iot.com",
    url="https://github.com/iotile/coretools/iotilesensorgraph",
    keywords=["iotile", "arch", "embedded", "hardware"],
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Software Development :: Libraries :: Python Modules"
        ],
    long_description="""\
iotile-emulate
--------------

A package that support emulating physical iotile devices based on python based emulation models.

See https://www.archsys.io.
"""
)
