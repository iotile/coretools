# IOTile Gateway
A python package for building a simple gateway that can talk to multiple IOTile devices

## Installation

```
pip install iotile-gateway
```
## Usage

The package installs one command line program `iotile-gateway` that can be invoked with no arguments to 
start a websockets server for bidirectional communication with IOTile devices.

```shell
> iotile-gateway
[C 161205 14:24:26 main:83] Starting websocket server on port 5120
[C 161205 14:24:27 bled112:509] BLED112 adapter supports 3 connections
```

You can cleanly exit the server using Ctrl+C.  If the server hangs on closing, you may have to kill the program
with kill on POSIX or with Ctrl+Break on Windows.  Any instance of the server hanging on exit is a bug that should
be reported immediately.

## Copyright and License

This code is distributed under the terms of the LGPL v3 license.
