# Release Notes

All major changes in each released version of iotile-emulate are listed here.

## HEAD

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