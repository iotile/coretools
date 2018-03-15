# Release Notes

All major changes in each released version of IOTileGateway are listed here.

## 1.5.3

- Rerelease of 1.5.2 with < 5.0.0 version spec instead of <= 5.0.0 in setup.py

## 1.5.2

- Fix tornado dependency to exclude v5.0.0 until we are properly compatible.

## 1.5.1

- Fix service_delegate tile init

## 1.5.0

- Add support for sending commands to services using IOTileSupervisor
- Refactor unit testing to make it easier to test tornado servers
- Refactor and fix IOTileSupervisor code
- Add iotile-send-rpc command for sending a RPC from the command line

## 1.4.0

- Fix exception hierarchy
- Make unit testing easier

## 1.3.4

- Fix headline status reporting to only report when it actually changes

## 1.3.3

- Add better granularity on service status change reporting

## 1.3.2

- Add the ability to store sticky headline messages for services and bug fixes

## 1.3.1

- Add the ability to store messages for services and bug fixes

## 1.3.0

- Add iotile-supervisor that can store and report on the status of services
  running on computer.  
- Add integration with iotile-supervisor from iotile-gateway

## 1.2.0

- Add support for gateway agents and better configurability

## 1.1.0

- Add support for monitoring device connection events
- Add support for streaming reports through IOTileGateway

## 1.0.0

- Initial public release of IOTileGateway