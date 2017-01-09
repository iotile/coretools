# Release Notes

All major changes in each released version of IOTileCore are listed here.

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
