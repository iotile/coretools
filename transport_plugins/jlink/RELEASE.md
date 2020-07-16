# Release Notes

All major changes in each released version of the jlink transport plugin are
listed here.

## 1.1.1

- Add placeholder support for heartbeat debug command.

## 1.1.0

- JLink adapter support for streaming and tracing

## 1.0.9

- Fixed bug in memory dump tool to correctly iterate read over large sizes

## 1.0.8

- Unpin dependency of iotile-core for iotile-core 5 release

## 1.0.7

- Improved error checking/messaging for `_read_memory_map`
- Fix `version.py` version number

## 1.0.6

- Added JLink functions like continue and register updating
- Integrated flash dump tool
- Add debug_read_memory()/debug_write_memory() function

## 1.0.5

- Fix `_try_connect` logic around already connected devices.

## 1.0.4

- Implement proper dependency major version limits.

## 1.0.3

- Remove missed builtins/__future__ calls

## 1.0.2

- Remove past/future/monotonic, pylint cleanup

## 1.0.1
- Drop python2 support 
- Enable python3 compatibility

## 0.3.2
- Fix setup.py info documentation string
- Add _open_streaming_interface function to the JLinkAdapter interface
-    Pytest Usage: ```py.test --port=jlink:mux=ftdi --device="device=nrf52;channel=3" --uuid=0 python/test```

## 0.3.1
- jlink checks if a disconnection is necessary prior to when attempting to connect or enter debug.

## 0.3.0
- jlink now only connects to device when connect_direct or debug is called
- debug has connection string as new optional parameter
- channel=index is used as a way to select multiplexing channel
- ftdi is one multiplexing architecture
- Usage: ```iotile hw --port jlink:mux=ftdi```, ```connect_direct device=nrf52;channel=0```,```debug -c device=nrf52;channel=0```

## 0.2.0

- Add support for sending scripts over jlink.  The scripts are internally just
  sent as a bunch of RPCs so there could be a possible speedup with better
  buffering but it works correctly.

## 0.1.0

- Initial public alpha release.  Includes support for sending commands to iotile
  devices through a shared memory RPC mechanism.
- Includes support for reflashing known chips over SWD using a JLink adapter.
