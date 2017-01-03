# Release Notes

All major changes in each released version of IOTileCore are listed here.

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
