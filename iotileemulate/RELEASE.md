# Release Notes

All major changes in each released version of iotile-emulate are listed here.

## HEAD

- Refactor for compatibility with latest coretools release that integrated asyncio
  support directly into CoreTools so it doesn't need to be bolted on anymore inside
  `iotile-emulate`

## 0.4.4

- Support busy response for RPCs in iotile-emulate. Issue #619
- Implement proper dependency major version limits. Since this package is still pre-1.0, we 
  still allow more breaking changes (in accordance with SemVer)

## 0.4.3

- Remove instances of builtins/__future__

## 0.4.2

- Make `EmulationLoop.finish_async_rpc` easier to use by automatically packing
  rpc responses.  Issue #721.
- Add support for raising `RPCRuntimeError` from an RPC implementation in order
  to return an error code.  This simplifies the implementation logic of complex
  RPCs.  Issue #718.
- Fixes bug inside CrossThreadResponse that does not properly reraise exceptions.

## 0.4.1

- Drop python2 support

## 0.3.1

- Fix streaming controller subsystem to properly mark streamers as complete
  so that streamers can send multiple reports.  Add test coverage to ensure that
  this is working.

## 0.3.0

- Update emulation_demo device to have its own proxy module for the demo tile.

- Increase documentation and review for accuracy after the asyncio port.

- MAJOR REFACTOR: All internal logic is moved to asyncio and python 2
  compatibility is dropped.  Previous callback code is converted to coroutines
  and support for backgrounds tasks is added to all tiles and controller 
  subsystems.

- Add support for hardware version RPC on the controller.  The default
  implementation returns the hardware string 'pythontile'

- Add support for loading and sgf file or string directly using a test_scenario
  registered on ReferenceController.  The sgf file is directly loaded into 
  persistent storage as well as the config_database.  An embedded app_tag is
  also set.

- Fix deadlock_check to work on multiple threads (not just the one that
  `__init__` was called on.).  Issue #638.

- Add support for notifying sensorgraph when a streaming interface is opened/
  closed.

- Add support into ReferenceController for setting app/os tags and versions.

- Improve SerializableState to allow for marking the object types of lists,
  properties and dicts to enable them to be properly serialized and
  deserialized without needing to explicitly call `mark_complex_type`.

## 0.2.0

- Add support for sending RPCs from the sensorgraph task in the reference 
  controller. The sensorgraph implementation should now be complete enough
  to run unmodified sensorgraphs including realtime data streaming.

- Add support for simulating the passage of time.  Time simulation is on by
  default for devices that inherit from ReferenceDevice and can be sped up
  by passing an `"accelerate_time": true` key or stopped by passing a 
  `"simulate_time": false` key.

- Cleanup and slightly refactor reset code.  Improve reset behavior to be more
  synchronous.

- Add support for asynchronous RPCs. Update the DemoDevice to have an async rpc
  implementation on the peripheral tile to test the async rpc implementation.

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
