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
        "pyparsing~=2.2.0",
        "toposort>=1.5,<2",
        "iotile-core>=5.0.0,<6"
    ],
    python_requires=">=3.5,<4",
    entry_points={'iotile.sg_processor': ['copy_all_a = iotile.sg.processors:copy_all_a',
                                          'copy_latest_a = iotile.sg.processors:copy_latest_a',
                                          'copy_count_a = iotile.sg.processors:copy_count_a',
                                          'call_rpc = iotile.sg.processors:call_rpc',
                                          'trigger_streamer = iotile.sg.processors:trigger_streamer',
                                          'subtract_afromb = iotile.sg.processors:subtract_afromb'],
                  'iotile.update_record': ['add_node = iotile.sg.update:AddNodeRecord',
                                           'add_streamer = iotile.sg.update:AddStreamerRecord',
                                           'set_config = iotile.sg.update:SetConfigRecord',
                                           'persist_graph = iotile.sg.update:PersistGraphRecord',
                                           'reset_graph = iotile.sg.update:ResetGraphRecord',
                                           'clear_data = iotile.sg.update:ClearDataRecord',
                                           'clear_configs = iotile.sg.update:ClearConfigVariablesRecord',
                                           'set_online = iotile.sg.update:SetGraphOnlineRecord',
                                           'set_constant = iotile.sg.update:SetConstantRecord'],
                  'iotile.virtual_tile': ['refcon_1 = iotile.sg.virtual.reference_controller:ReferenceController'],
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
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Software Development :: Libraries :: Python Modules"
        ],
    long_description="""\
IOTileSensorGraph
-----------------

A package that parses, optimizes and runs sensor graph scripts.

See https://www.arch-iot.com.
"""
)
