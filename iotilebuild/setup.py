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

setup(
    name="iotile-build",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    install_requires=[
        "breathe>=4.30",
        "crcmod>=1.7",
        "iotile-core>=5.2",
        "jinja2>=3",
        "pygtrie>=2",
        "setuptools>=57",
        "sphinx>=4",
        "toposort>=1.6",
        "pycparser>=2.20",
        "pyparsing~=2.2.0",
        "scons>=4.1",
        "wheel>=0.33",
    ],
    python_requires=">=3.7,<4",
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
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Software Development :: Libraries :: Python Modules"
        ],
    long_description="""\
IOTileBuild
-----------

A python package for building embedded firmware on IOTile based devices.  See https://www.arch-iot.com.
"""
)
