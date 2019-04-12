# Release Notes

All major changes in each released version of the websocket transport plugin are listed here.

## HEAD

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