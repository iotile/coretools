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
    name="iotile-sensorgraph",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    description="IOTile SensorGraph Management and Simulation Package",
    install_requires=[
        "pyparsing>=2.2.0",
        "future>=0.16.0",
        "monotonic>=1.3.0",
        "toposort>=1.5",
        "iotile-core>=3.16.7"
    ],
    entry_points={'iotile.sg_processor': ['copy_all_a = iotile.sg.processors:copy_all_a',
                                          'copy_latest_a = iotile.sg.processors:copy_latest_a',
                                          'copy_count_a = iotile.sg.processors:copy_count_a',
                                          'call_rpc = iotile.sg.processors:call_rpc',
                                          'trigger_streamer = iotile.sg.processors:trigger_streamer',
                                          'subtract_a_from_b = iotile.sg.processors:subtract_a_from_b'],
                  'iotile.update_record': ['add_node = iotile.sg.update:AddNodeRecord',
                                           'add_streamer = iotile.sg.update:AddStreamerRecord',
                                           'set_config = iotile.sg.update:SetConfigRecord',
                                           'persist_graph = iotile.sg.update:PersistGraphRecord',
                                           'reset_graph = iotile.sg.update:ResetGraphRecord',
                                           'clear_data = iotile.sg.update:ClearDataRecord',
                                           'set_online = iotile.sg.update:SetGraphOnlineRecord',
                                           'set_constant = iotile.sg.update:SetConstantRecord',
                                           'set_version = iotile.sg.update:SetDeviceTagRecord'],
                  'console_scripts': ['iotile-sgrun = iotile.sg.scripts.iotile_sgrun:main',
                                      'iotile-sgcompile = iotile.sg.scripts.iotile_sgcompile:main']},
    author="Arch",
    author_email="info@arch-iot.com",
    url="https://github.com/iotile/coretools/iotilesensorgraph",
    keywords=["iotile", "arch", "embedded", "hardware"],
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules"
        ],
    long_description="""\
IOTileSensorGraph
-----------------

A package that parses, optimizes and runs sensor graph scripts.

See https://www.arch-iot.com.
"""
)
