from setuptools import setup, find_packages

import version

setup(
    name="iotile-ext-cloud",
    packages=find_packages(exclude=("test",)),
    version=version.version,
    license="LGPLv3",
    install_requires=[
        "iotile-core>=3.6.2",
        "iotile_cloud>=0.8.11"
    ],

    entry_points={'iotile.config_function': ['link_cloud = iotile.cloud.config:link_cloud'],
                  'iotile.config_variables': ['iotile-ext-cloud = iotile.cloud.config:get_variables'],
                  'iotile.plugin': ['cloud = iotile.cloud.plugin:setup_plugin'],
                  'iotile.app': ['cloud_uploader = iotile.cloud.apps.cloud_uploader']},

    description="IOTile.cloud integration into CoreTools",
    author="Arch",
    author_email="info@arch-iot.com",
    url="http://github.com/iotile/lib_iotilecore",
    keywords=["iotile", "arch", "embedded", "hardware", "firmware"],
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules"
        ],
    long_description="""\
IOTile Cloud Extensions
-----------------------

A set of extensions to IOTile CoreTools that allow you to interact with iotile.cloud.
See https://www.arch-iot.com.
"""
)
