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
    name="iotile-test",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    description="IOTile Test Infrastructure",
    python_requires=">=3.5,<4",
    entry_points={'iotile.virtual_device': ['simple = iotile.mock.devices.simple_virtual_device:SimpleVirtualDevice',
                                            'report_test = iotile.mock.devices.report_test_device:ReportTestDevice',
                                            'realtime_test = iotile.mock.devices.realtime_test_device:RealtimeTestDevice',
                                            'no_app = iotile.mock.devices.noapp:NoAppVirtualDevice',
                                            'tracing_test = iotile.mock.devices.tracing_test_device:TracingTestDevice',
                                            'sg_test = iotile.mock.devices.sg_test_device:SensorGraphTestDevice'],
                  'iotile.proxy': ['simple = iotile.mock.devices.simple_virtual_proxy',
                                   'report_test = iotile.mock.devices.report_test_device_proxy'],
                  'console_scripts': ['prepare_device = iotile.test_scripts.prepare_device:main']},
    author="Arch",
    author_email="info@arch-iot.com",
    url="https://github.com/iotile/coretools/iotilecore",
    keywords=["iotile", "arch", "embedded", "hardware"],
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        ],
    long_description="""\
IOTileTest
----------

A python package for testing IOTile based infrastructure including mocks for major portions.

See https://www.arch-iot.com.
"""
)
