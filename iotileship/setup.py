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
    name="iotile-ship",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    install_requires=[
        "iotile-core>=3.12.0",
        "pyaml>=17.12.0"
    ],
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'iotile-ship = iotile.ship.scripts.iotile_ship:main'
        ],
        'iotile.recipe_action': [
            'PromptStep         = iotile.ship.actions.prompt_step:PromptStep',
            'WaitStep           = iotile.ship.actions.wait_step:WaitStep',
            'PipeSnippetStep    = iotile.ship.actions.pipe_snippet_step:PipeSnippetStep',
            'SyncCloudStep      = iotile.ship.actions.sync_cloud_step:SyncCloudStep',
            'SyncRTCStep        = iotile.ship.actions.sync_rtc_step:SyncRTCStep',
            'VerifyDeviceStep   = iotile.ship.actions.verify_device_step:VerifyDeviceStep',
            'SendOTAScriptStep  = iotile.ship.actions.send_ota_script_step:SendOTAScriptStep'
        ],
        'iotile.recipe_resource': [
            'hardware_manager   = iotile.ship.resources:HardwareManagerResource'
        ],
        'iotile.autobuild': [
            'autobuild_shiparchive = iotile.ship.autobuild:autobuild_shiparchive'
        ]
    },
    description="IOTile Ship Support",
    author="Arch",
    author_email="info@arch-iot.com",
    url="http://github.com/iotile/coretools/iotileship",
    keywords=["iotile", "arch", "embedded", "hardware", "firmware"],
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules"
        ],
    long_description="""\
IOTileship
-----------

A python package for shiping embedded firmware on IOTile based devices.  See https://www.arch-iot.com.

IOTileship embeds SCons in accordance with its license permitting redistribution.  More information on
SCons can be found at: https://scons.org
"""
)
