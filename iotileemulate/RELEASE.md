# Release Notes

All major changes in each released version of iotile-emulate are listed here.

## HEAD

- Cleanup and slightly refactor reset code.  Improve reset behavior to be more
  synchronous.

- Add support for asynchronous RPCs.

- Update the DemoDevice to have an async rpc implementation on the peripheral
  tile to test the async rpc implementation.

- Update base classes for EmulatedDevice and EmulatedTile to not be 
  importable via `ComponentRegistry.load_extensions()` so that they are not
  imported multiple times when trying to import their subclasses.

## 0.0.1

- Add support for EmulatedDevice and EmulatedTile classes.  These classes allow
  for the creation of virtual devices that emulate physical devices with support
  for state snapshotting to save/load device state and test scenarios to allow
  easy creation of complex device states for integration testing.

- Add support for new DeviceAdapter named EmulatedDeviceAdapter.  This is a 
  subclass of VirtualDeviceAdapter will all of the same features except that it
  only works with EmulatedDevices and it provides a debug interface that allows
  you to save and load state as well as load scenarios and track changes on your
  emulated devices.

  It includes additional methods on DebugManager in order to make these new
  functions accessible.

- Move ReferenceDevice and ReferenceController to EmulatedDevice and
  EmulatedTile subclasses and begin refactor to split out individual controller
  subsystems to allow for the rest of the reference IOTile controller
  functionality to be added.

- Start adding global constants with good docstring descriptions to be used as
  a basis for automatic help text generation or documentation.

- Adds test coverage of tile_manager and config_database subsystems.

- Moves all emulated RPCs to a single background thread so that we can support
  sending rpcs from multiple threads without race conditions.

- Add support for the RawSensorLog task including pushing and dumping streams.

- Refactor controller reset procedure to include a clear list of reset
  tasks that happen synchronously in the emulation thread.

- Add support for properly resetting the sensor_log subsystem and latching in
  the state of the fill/stop config variable.

- Add initial support for the sensor_graph subsystem except for dump/restore
  and streamer support.  Initial RPCs are added as well except those dealing
  with streamers.

- Finish basic streamer support except for seeking and querying

- Add clock manager subsystem with support for uptime and utc based
  timestamping.
