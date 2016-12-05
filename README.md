## Core IOTile Tools

This repository contains the basic infrastructure needed build and interact with 
IOTile based devices.  It is divided into a set of python packages that work 
together to create an extensible but easy to use framework that supports any 
IOTile device.

### IOTile-Core Status

[![PyPI version](https://badge.fury.io/py/iotile-core.svg)](https://badge.fury.io/py/iotile-core)

### IOTile-Build Status

[![PyPI version](https://badge.fury.io/py/iotile-build.svg)](https://badge.fury.io/py/iotile-build)

### IOTile-Transport-BLED112 Status

[![PyPI version](https://badge.fury.io/py/iotile-transport-bled112.svg)](https://badge.fury.io/py/iotile-transport-bled112)

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

### Installing Support for IOTile Based Devices

CoreTools just gives you the framework to interact with IOTile based devices. 
In order to control any given IOTile device, you need to also install a support
package that contains support for that device.  Support packages extend CoreTools
to provide support for specific tiles.  

There are currently no publicly available support packages, so please contact
Arch to get access to private support packages.

### License

This software is released under the terms of the LGPL v3 license.  It includes
pieces that are distributed under the terms of their own licenses.  A list of 
included 3rd party software is described in the README files for each component
of IOTile CoreTools.
