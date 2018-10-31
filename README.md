## Core IOTile Tools

<!-- MarkdownTOC autolink="true" bracket="round" -->

- [Build Status](#build-status)
	- [Core Packages](#core-packages)
	- [Built-in Device Transport Protocols](#built-in-device-transport-protocols)
- [Installation \(from PyPI\)](#installation-from-pypi)
- [Working with Encrypted Device Data](#working-with-encrypted-device-data)
- [Installing Support for IOTile Based Devices](#installing-support-for-iotile-based-devices)
- [Continuous Deployment](#continuous-deployment)
- [Manually Releasing](#manually-releasing)
- [License](#license)

<!-- /MarkdownTOC -->


[![Build Status](https://travis-ci.org/iotile/coretools.svg?branch=master)](https://travis-ci.org/iotile/coretools)
[![Build status](https://ci.appveyor.com/api/projects/status/yu3q8m8dm6aqoc6e/branch/master?svg=true)](https://ci.appveyor.com/project/timburke/coretools/branch/master)

This repository contains the basic infrastructure needed build and interact with 
IOTile based devices.  It is divided into a set of python packages that work 
together to create an extensible but easy to use framework that supports any 
IOTile device.

Read the latest [Documentation](http://coretools.readthedocs.io/en/latest/)!

### Build Status

#### Core Packages

> These are the building blocks that make up CoreTools.  Depending on your particular
> use case, you may need just one of them or you may use them all.  

| Tool         | Description |PyPI Version                                                                                                 |
|--------------|-------------|-------------------------------------------------------------------------------------------------------------|
|iotile-core   |The central package of CoreTools, includes the core plugin architecture and device communication system|[![PyPI version](https://badge.fury.io/py/iotile-core.svg)](https://badge.fury.io/py/iotile-core)             |
|iotile-build  |A build system for creating IOTile device firmware that is controllable from CoreTools|[![PyPI version](https://badge.fury.io/py/iotile-build.svg)](https://badge.fury.io/py/iotile-build)           |
|iotile-gateway|A multi-user, multi-device transparent proxy for IOTile devices|[![PyPI version](https://badge.fury.io/py/iotile-gateway.svg)](https://badge.fury.io/py/iotile-gateway)       |
|iotile-sensorgraph|A simulator for the embedded sensorgraph engine included in some IOTile device firmware|[![PyPI version](https://badge.fury.io/py/iotile-sensorgraph.svg)](https://badge.fury.io/py/iotile-sensorgraph)|
|iotile-emulate|A complete set of emulation tools for emulating physical iotile devices|[![PyPI version](https://badge.fury.io/py/iotile-emulate.svg)](https://badge.fury.io/py/iotile-emulate)|
|iotile-ship|A manufacturing tool that lets you define repeatable recipes to bring up IOTile based hardware at a factory|[![PyPI version](https://badge.fury.io/py/iotile-ship.svg)](https://badge.fury.io/py/iotile-ship)                |
|iotile-test|Internal test harnesses and mocks to test the rest of CoreTools and applications built using CoreTools|[![PyPI version](https://badge.fury.io/py/iotile-test.svg)](https://badge.fury.io/py/iotile-test)             |
|iotile-ext-cloud|A CoreTools-like wrapper for interacting with IOTile.cloud, a cloud based device management system that works well with IOTile based devices|[![PyPI version](https://badge.fury.io/py/iotile-ext-cloud.svg)](https://badge.fury.io/py/iotile-ext-cloud)   |

#### Built-in Device Transport Protocols

> CoreTools is inherently agnostic in how it connects to an IOTile Device.  Many
> physical IOTile devices use Bluetooth Low Energy to communicate with the external
> world but this is not an intrinsic assumption of how CoreTools works.
>
> The currently included protocols are shown below.

| Tranport Plugin         | Description | PyPI Version                                                                                                 |
|-------------------------|-------------|--------------------------------------------------------------------------------------------------------------|
|iotile-transport-nativeble|Connects to IOTile devices over BLE using the cross-platform baBLE project to use your computers native bluetooth stack|[![PyPI version](https://badge.fury.io/py/iotile-transport-nativeble.svg)](https://badge.fury.io/py/iotile-transport-nativeble)|
|iotile-transport-websocket|Connects to IOTile devices over websockets|[![PyPI version](https://badge.fury.io/py/iotile-transport-websocket.svg)](https://badge.fury.io/py/iotile-transport-)|
|iotile-transport-bled112|Connects to IOTile devices over BLE using the BLED112 USB dongle by Silicon Labs|[![PyPI version](https://badge.fury.io/py/iotile-transport-bled112.svg)](https://badge.fury.io/py/iotile-transport-bled112)|
|iotile-transport-jlink|Connects to an IOTile device using a physical SWD debug connection through a Segger JLink emulator|[![PyPI version](https://badge.fury.io/py/iotile-transport-jlink.svg)](https://badge.fury.io/py/iotile-transport-jlink)|

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
