# Release Notes

All major changes in each released version of the websocket transport plugin are listed here.

## HEAD

- Remove debug logger level to lower the chattiness of the transport plugin
- Fix python 3 compatibility issue when calling an RPC that throws an exception.
  (Issue #639)
- open_debug_interface has optional argument connection_string

## 1.0.0

- Initial public release of the Websocket transport plugin