# Release Notes

All major changes in each released version of the jlink transport plugin are
listed here.

## HEAD

## 0.2.0

- Add support for sending scripts over jlink.  The scripts are internally just
  sent as a bunch of RPCs so there could be a possible speedup with better
  buffering but it works correctly.

## 0.1.0

- Initial public alpha release.  Includes support for sending commands to iotile
  devices through a shared memory RPC mechanism.
- Includes support for reflashing known chips over SWD using a JLink adapter.
