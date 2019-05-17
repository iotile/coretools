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
#
# NB There is a required manual post-install step to register iotilebuild with the iotile command
# so that you can use the iotile build command.  Run
# > iotile registry add_plugin build iotilebuild.build.build,build

from setuptools import setup, find_packages
import version

embedded_scons = "3.0.1"

setup(
    name="iotile-build",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    install_requires=[
        "crcmod>=1.7.0",
        "iotile-core>=5.0.0,<6",
        "sphinx>=2,<3",
        "jinja2>=2.10.0,<3",
        "breathe>=4.11.0,<5",
        "pygtrie>=2.0.0,<3",
        "toposort>=1.5.0,<2",
        "wheel>=0.33",
        "setuptools>=40.8",
        "pycparser>=2.17,<3",
        "pyparsing~=2.2.0"
    ],
    python_requires=">=3.5,<4",
    include_package_data=True,
    entry_points={'iotile.plugin': ['.build = iotile.build.plugin:setup_plugin'],
                  'iotile.build.default_depresolver': ['registry_resolver = iotile.build.dev.resolvers:DEFAULT_REGISTRY_RESOLVER'],
                  'iotile.build.depresolver': ['ComponentRegistryResolver = iotile.build.dev.resolvers.registry_resolver:ComponentRegistryResolver'],
                  'iotile.build.release_provider': ['null = iotile.build.release.null_provider:NullReleaseProvider',
                                                    'pypi = iotile.build.release.pypi_provider:PyPIReleaseProvider'],
                  'iotile.config_variables': ['iotile-build = iotile.build.config_variables:get_variables'],
                  'console_scripts': ['iotile-tbcompile = iotile.build.scripts.iotile_tbcompile:main',
                                      'iotile-emulate = iotile.build.scripts.iotile_emulate:main']},
    description="IOTile Build Support",
    author="Arch",
    author_email="info@arch-iot.com",
    url="http://github.com/iotile/lib_iotilecore",
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
IOTileBuild
-----------

A python package for building embedded firmware on IOTile based devices.  See https://www.arch-iot.com.

IOTileBuild embeds SCons in accordance with its license permitting redistribution.  More information on
SCons can be found at: https://scons.org
"""
)
