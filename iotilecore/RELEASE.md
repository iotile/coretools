# Release Notes

All major changes in each released version of IOTileCore are listed here.

## 3.9.4

- Allow KVStore to be backed by a JSON file or SQLite and add test coverage to make sure
  that ComponentRegistry, which is based on KVStore works correctly with both backing store
  types.

## 3.9.3

- Fix KVStore to not make a directory in user's home folder when iotile-core is installed
  in a virtual environment.

## 3.9.2

- Fix iotile script to not hang on exit if an uncaught exception happens and we are connected
  to a hardware device.

## 3.9.1

- Update virtual_device to be able to find devices in python files that are not installed.
  You just pass the path to the file rather than a name of an installed virtual device.

## 3.9.0

- Fix hash calculation to include footer in SignedListReport
- Add new functionality for waiting in AdapterStream until scanned devices are seen when
  connect is called for the first time. 

## 3.8.1

- Fix bug finding TileBusProxyObject when a tile does not have any application firmware installed
  and add test coverage for this.

## 3.8.0

- Add support for AuthProviders that can sign/verify/encrypt/decrypt data.  This functionality
  is needed for verifying the signatures on reports received from the devices and creating
  signed reports.

- Add default ChainedAuthProvider that provides report signing and verifying using either
  SHA256 hashes (for integrity only) or HMAC-SHA256 using a key stored in an environment
  variable.

- Add support for running virtual_devices direcly without a loopback adapter.  You can use
  the virtual:<device_name>@path_to_config_json connection string to connect to the device
  by its uuid.

- Add test coverage for signing and verifying reports.


## 3.7.0

- Add SignedList report format for streaming signed lists of multiple readings in
  a single report

## 3.6.2

- Add audit message for error streaming report

## 3.6.1

- Provide generic implementation of report chunking and streaming.

## 3.6.0

- Create a virtual device interface for serving access to virtual iotile devices that
  let people connect to computers like you connect to any other IOTile device.
- Add virtual_device script to make it easy to setup a virtual iotile device.

## 3.5.3

- Update IOTile to find component dependencies listed in architecture overlays as
  well as those listed for a module and for an architecture.

## 3.5.2

- Add the concept of coexistence classes to SemanticVersion objects so that you 
  can easily see which are compatible with each other in a semanic versioning sense

## 3.5.1

- Add the ability to specify a key function to SemanticVersionRange.filter

## 3.5.0

- Add SemanticVersionRange object that supports defining basic ranges of semantic versions
  and checking if SemanticVersion objects are contained within them.  Currently only supports
  ^X.Y.Z ranges and * wildcard ranges.
- Properly parse the semantic version range specified in an IOTile component.

## 3.4.0

- Add support for sorting SemanticVersion objects and explicitly allow only a finite number
  of types of prereleases (build, alpha, beta and rc).  There is a total ordering of
  SemanticVersion objects where releases are better than prereleases and prereleases are ordered
  by build < alpha < beta < rc.  Each prerelease needs to be numbered like alpha1, rc5 etc.

## 3.3.0

- Add support for storing release steps in module_settings.json and parsing release steps
  in IOTile objects.  This will allow iotile-build and others to provide the ability to 
  release built IOTileComponents for public or private distribution automatically.

## 3.2.0

- Add support for storing config settings in per virtualenv registry

## 3.1.1

- Add support for error checking in AdapterStream to catch errors connecting to a device
  or opening interfaces and convert them into HardwareErrors

## 3.1.0

- Add support for report streaming from IOTile devices through iotile-core and associated
  projects.

## 3.0.0

- Initial public release
