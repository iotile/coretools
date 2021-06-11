# Release Notes

All major changes in each released version of the websocket transport plugin are listed here.

## 3.2.0

- removed 3.6 support due to asyncio API change in 3.7
- Python 3.9 support

## 3.1.1

- Python compatibility set to 3.6-3.8 because of py35 EOL

## 3.1.0

 - SRefactored plugin to allow for additional socket transports. Now depends on the new iotile_transport_socket_lib package.

## 3.0.0

- Completely refactor to be based on `asyncio` and the `websockets` package
  instead of ws4py and an older package as well as tornado.
- Completely remove legacy VirtualInterface that has been supplanted by DeviceServer.

## 2.0.3

- Implement proper dependency major version limits.

## 2.0.2

- Remove past/future/monotonic, pylint cleanup

## 2.0.1

- Remove debug logger level to lower the chattiness of the transport plugin
- Fix python 3 compatibility issue when calling an RPC that throws an exception.
  (Issue #639)
- open_debug_interface has optional argument connection_string
- Drop python2 support

## 1.0.0

- Initial public release of the Websocket transport plugin
