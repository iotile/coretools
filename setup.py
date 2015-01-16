from setuptools import setup, find_packages
setup(
    name = "pymomo",
    packages = find_packages(),
    version = "1.0.1",
    install_requires=[
        "beautifulsoup4==4.3.2",
        "BTrees==4.1.1",
        "Cheetah==2.4.4",
        "cmdln==1.1.2",
        "colorama==0.3.3",
        "decorator==3.4.0",
        "dirspec==13.10",
        "intelhex==1.5",
        "Markdown==2.5.2",
        "nose==1.3.4",
        "persistent==4.0.8",
        "py==1.4.26",
        "pycparser==2.10",
        "pyparsing==2.0.3",
        "pyserial==2.7",
        "pytest==2.6.4",
        "six==1.9.0",
        "transaction==1.4.3",
        "zc.lockfile==1.1.0",
        "ZConfig==3.0.4",
        "zdaemon==4.0.1",
        "ZEO==4.1.0",
        "ZODB==4.1.0",
        "ZODB3==3.11.0",
        "zope.interface==4.1.2"
    ],
    package_data={
        'pymomo': ['config/*']
    },
    description = "WellDone Mobile Monitor (MoMo) Interaction Library",
    author = "WellDone International",
    author_email = "info@welldone.org",
    url = "http://github.com/welldone/pymomo",
    keywords = ["momo", "remote", "monitoring", "embedded", "hardware"],
    classifiers = [
        "Programming Language :: Python",
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules"
        ],
    long_description = """\
PyMoMo
------

A python library for interacting with MoMo devices.  See https://momo.welldone.org.

"""
)