"""Setup file for iotile-core."""

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
    name="iotile-core",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    install_requires=[
        "python-dateutil>=2.8.0,<3",
        "typedargs>=1.0.0,<2",
        "sortedcontainers~=2.1",
        "entrypoints>=0.3.0,<1"
    ],
    extras_require={
        'ui': ["asciimatics>=1.10.0,<2"]
    },
    entry_points={
        'console_scripts': [
            'iotile = iotile.core.scripts.iotile_script:main',
            'virtual_device = iotile.core.scripts.virtualdev_script:main',
            'iotile-updateinfo = iotile.core.scripts.iotile_updateinfo_script:main'
        ],
        'iotile.device_adapter': [
            'virtual = iotile.core.hw.transport:VirtualDeviceAdapter'
        ],
        'iotile.report_format': [
            'individual = iotile.core.hw.reports:IndividualReadingReport',
            'signed_list = iotile.core.hw.reports:SignedListReport',
            'broadcast = iotile.core.hw.reports:BroadcastReport'
        ],
        'iotile.auth_provider': [
            'BasicAuthProvider = iotile.core.hw.auth.basic_auth_provider:BasicAuthProvider',
            'EnvAuthProvider = iotile.core.hw.auth.env_auth_provider:EnvAuthProvider',
            'ChainedAuthProvider = iotile.core.hw.auth.auth_chain:ChainedAuthProvider'
        ],
        'iotile.default_auth_providers': [
            'BasicAuthProvider = iotile.core.hw.auth.default_providers:DefaultBasicAuth',
            'EnvAuthProvider = iotile.core.hw.auth.default_providers:DefaultEnvAuth'
        ],
        'iotile.config_variables': [
            'iotile-core = iotile.core.config_variables:get_variables'
        ],
        'iotile.virtual_device': [
            'tile_based = iotile.core.hw.virtual.tile_based_device:TileBasedVirtualDevice'
        ],
        'iotile.recipe_action': [
            'FlashBoardStep = iotile.core.hw.debug.flash_board_step:FlashBoardStep'
        ],
        'iotile.app': [
            'device_info = iotile.core.hw.app.info_app',
            'device_updater = iotile.core.hw.app.updater_app'
        ]
    },
    description="IOTile Core Tools",
    author="Arch",
    author_email="info@arch-iot.com",
    url="https://github.com/iotile/coretools/iotilecore",
    keywords=["iotile", "arch", "embedded", "hardware"],
    python_requires=">=3.5, <4",
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
IOTileCore
----------

A python package for interacting with IOTile based devices.  See https://www.arch-iot.com.

"""
)
