## Core IOTile Tools

<!-- MarkdownTOC autolink="true" bracket="round" -->

- [Build Status](#build-status)
- [Installation \(from PyPI\)](#installation-from-pypi)
- [Working with Encrypted Device Data](#working-with-encrypted-device-data)
- [Installing Support for IOTile Based Devices](#installing-support-for-iotile-based-devices)
- [Continuous Deployment](#continuous-deployment)
- [Manually Releasing](#manually-releasing)
- [License](#license)

<!-- /MarkdownTOC -->


[![Build Status](https://travis-ci.org/iotile/coretools.svg?branch=master)](https://travis-ci.org/iotile/coretools)
[![Build status](https://ci.appveyor.com/api/projects/status/yu3q8m8dm6aqoc6e/branch/master?svg=true)](https://ci.appveyor.com/project/timburke/coretools/branch/master)
[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bgithub.com%2Fiotile%2Fcoretools.svg?type=shield)](https://app.fossa.io/projects/git%2Bgithub.com%2Fiotile%2Fcoretools?ref=badge_shield)

This repository contains the basic infrastructure needed build and interact with 
IOTile based devices.  It is divided into a set of python packages that work 
together to create an extensible but easy to use framework that supports any 
IOTile device.

Read the latest [Documentation](http://coretools.readthedocs.io/en/latest/)!

### Build Status

| Tool         | PyPI Version                                                                                                 |
|--------------|--------------------------------------------------------------------------------------------------------------|
|IOTile-Core   |[![PyPI version](https://badge.fury.io/py/iotile-core.svg)](https://badge.fury.io/py/iotile-core)             |
|IOTile-Build  |[![PyPI version](https://badge.fury.io/py/iotile-build.svg)](https://badge.fury.io/py/iotile-build)           |
|IOTile-Gateway|[![PyPI version](https://badge.fury.io/py/iotile-gateway.svg)](https://badge.fury.io/py/iotile-gateway)       |
|IOTile-SensorGraph|[![PyPI version](https://badge.fury.io/py/iotile-sensorgraph.svg)](https://badge.fury.io/py/iotile-sensorgraph)|
|IOTile-Ship|[![PyPI version](https://badge.fury.io/py/iotile-ship.svg)](https://badge.fury.io/py/iotile-ship)                |
|IOTile-Test   |[![PyPI version](https://badge.fury.io/py/iotile-test.svg)](https://badge.fury.io/py/iotile-test)             |
|IOTile-Cloud  |[![PyPI version](https://badge.fury.io/py/iotile-ext-cloud.svg)](https://badge.fury.io/py/iotile-ext-cloud)   |
|BLED112-Plugin|[![PyPI version](https://badge.fury.io/py/iotile-transport-bled112.svg)](https://badge.fury.io/py/iotile-transport-bled112)|

### Installation (from PyPI)

The core set of tools is divided into three pip installable packages

```shell
pip install iotile-core iotile-transport-bled112
```

If you also wish to use the IOTile build system to build IOTile components, you
should also install IOTile-Build

```shell
pip install iotile-build
```

If you want to use the IOTile testing tools (necessary for testing CoreTools among other uses,

```shell
pip install iotile-test
```

### Working with Encrypted Device Data

If your devices are configured to protect the report data that they produce, you
need to install `pycrypto` in order to CoreTools to be able to decrypt report 
data.  This is only necessary to view encrypted report data and, obviously, 
also requires that you have access to the device in question's signing key.

Pycrypto can be installed using:

```
pip install pycrypto
```

If you are running on Windows, you may not have a compiler installed that is
able to compile the PyCrypto package.  Microsoft provides a free compiler that
is easily installed [here](https://www.microsoft.com/en-us/download/details.aspx?id=44266).

### Installing Support for IOTile Based Devices

CoreTools just gives you the framework to interact with IOTile based devices. 
In order to control any given IOTile device, you need to also install a support
package that contains support for that device.  Support packages extend CoreTools
to provide support for specific tiles.  

There are currently no publicly available support packages, so please contact
Arch to get access to private support packages.

### Continuous Deployment
Automatic release to pypi is handled by Travis CI every time a new tag is created
on the master branch.  The tags must have a specific naming format:

```
<distribution_name>-<version>
```

Where `<distribution_name>` is the name of a specific component of CoreTools.  Currently,
the known components are:

```
iotilecore
iotilebuild
iotilegateway
iotile_transport_bled112
iotile_transport_awsiot
iotiletest
iotilesensorgraph
```

The version must match the version that is encoded in version.py in the corresponding python
distribution to be released and is checked in the release.py script before attempting to release.

### Manually Releasing

Releasing new builds to pypi is handled by the `scripts/release.py` script.  The 
script should be called with one argument, which is the name and version of the
distribution being released.  

First, make sure all build requirements are satisfied:

```shell
> pip install -r build_requirements.txt
```

Then, release (for example iotilecore-X.Y.Z) using
```shell
> python scripts/release iotilecore-X.Y.Z
```

You need to have the following environment variables set correctly with pypi and slack
secrets:

```
PYPI_USER
PYPI_PASS
SLACK_WEB_HOOK
```

### License

This software is released under the terms of the LGPL v3 license.  It includes
pieces that are distributed under the terms of their own licenses.  A list of 
included 3rd party software is described in the README files for each component
of IOTile CoreTools.


[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bgithub.com%2Fiotile%2Fcoretools.svg?type=large)](https://app.fossa.io/projects/git%2Bgithub.com%2Fiotile%2Fcoretools?ref=badge_large)