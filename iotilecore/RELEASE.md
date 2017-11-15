# Release Notes

All major changes in each released version of IOTileCore are listed here.

## 3.16.4

- Follow symlinks if needed during the rename operation in JSONKVStore save method

## 3.16.3

- Add support for =X.Y.Z version range specifier in addition to the already
  supported ^X.Y.Z specifier.

## 3.16.2

- Add support for additional virtual_interface audit message then there is an
  error responding to an RPC that could not be corrected with a retry.

## 3.16.1

- Allow StoppableWorkerThread to have no timeout.  This allows for using 
  generator functions that themselves wait for some external event and hence
  the extra sleep calls are superfluous.

## 3.16.0

- Add support for encrypting reports when a signing key is available.

## 3.15.3

- Add support for sorting scan results and limiting the number of results returned

## 3.15.2

- Add support for setting values in SparseMemory object.

## 3.15.1

- Improve the performance of ComponentRegistry by not rescanning all plugins
  every time it is loaded.

## 3.15.0

- Add support for tile modular tile based virtual devices with a new
  tile_based virtual device that allows you to configure what tiles it
  contains
- Add a VirtualTile class hierarchy to mirror the VirtualIOTileDevice
  class hierarchy

## 3.14.5

- Fix argument format on exception call inside virtualdevice

## 3.14.4

- Now using optional kwarg 'arg_format' in TileBusProxyObject's rpc method to
  allow calling code to not have to manually pack arguments

## 3.14.3

- Fix virtual device adapter to properly allow connecting to devices by setting
  the probe_required flag.

## 3.14.2

- Allow specifying sent streamer and timestamp when creating signed list reports

## 3.14.1

- Allow specifying the streamer selector and report id when creating signed list
  reports.

## 3.14.0

- Fix exception hierarchy to remove EnvironmentError and TimeoutError that
  shadow builtin exceptions

## 3.13.4

- Add better exception message when there are invalid arguments or response 
  to a virtual device.

## 3.13.3

- Make StoppableThread stop faster when you configure a large interval for 
  the thread function to run at.

## 3.13.2

- Add support for float validator

## 3.13.1

- Improve schema validator support

## 3.13.0

- Add support for validating documents using schema validator
- Add support for standard websocket client using schema validator
  to dispatch messages to handlers
- Add better support for virtaul virtual devices to allow realtime streaming
  of data from the devices rather than just on connection

## 3.12.4

- Fix handling of virtual interface config data that checked for the wrong
  dictionary key

## 3.12.3

- Add the ability to have configuration functions loaded in ConfigManager
  the same way that we have config variables.  This is needed by
  iotile-ext-cloud to support storing persistent cloud tokens.
- Increase test coverage

## 3.12.2

- Add the ability to load virtual devices from python modules that have not
  been installed using pip.  Just pass the path to the python file rather than
  the name of the pkg_resources entrypoint.  For example to load ./device.py
  as a virtual device, using iotile hw --port=virtual:./device.py

## 3.12.1

- Fix ConfigManager on tile proxy objects.  There was an infinite loop in 
  list_variables and the other methods were poorly documented.

## 3.12.0

- Add support for ConfigManager that supports typed configuration variables
  that can be registered by coretools plugins.
- Fix nuisance exceptions in iotile shell when parameters are not convertable
  to their correct types.

## 3.11.0

- Add support for SparseMemory object that can use used to represent slices
  of memory downloaded from a device.  This is the first debug feature present
  in iotilecore.

## 3.10.3

- Remove debug print statement that got kept in released version

## 3.10.2

- Add support for forcing the registry to be a specific type; either json or sqlite
  are currently supported.  You can place a registry_type.txt file containing the 
  word json or sqlite in the folder next to the component_registry.* file and it will
  choose json or sqlite based on what you put in the file throwing an error if a random
  word is entered.

## 3.10.1

- Add support for tracing from virtual devices over virtual interfaces

## 3.10.0

- Add support for a tracing interface.  The tracing interface allows sending an unstructured
  stream of debug data from an IOTile device and dumping it to stdout or a file using the
  iotile tool.

## 3.9.5

- Make scan wait for min_scan interval before returning if a HardwareManager is immediately
  created.  This fixes the same issue for scanning that could cause connections to fail.

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
