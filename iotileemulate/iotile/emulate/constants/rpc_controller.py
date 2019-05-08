"""RPCs that are implemented by a tilebus controller outside of a subsystem.

These are generic RPCs that set configuration information for the entire
device or store persistent metadata like app or os tags.
"""

from iotile.core.hw.virtual import RPCDeclaration


SET_OS_APP_TAG = RPCDeclaration(0x100B, "LLBB", "L")
"""Update the OS and/or APP tag of the device.

The OS and APP tags are 20 bit numerical identifiers that identify the
firmware and sensorgraph, respectively running on an IOTile device.  They have
an associated X.Y version number for each tag that identifies the version
of os or app running on the device.

Each tag is packed into a 32-bit (little endian) number in the following
way:

lowest 20 bits: the numerical tag identifier
6 bits: the minor version number
6 bits: the major version number

So the highest 12 bits are a 6.6 fixed point integer storing MAJOR.MINOR
version numbers and the lowest 20 bits are the numerical tag value itself.

This RPC can update both tags/versions at the same time, only one or neither
based on the flags included in the RPC call.

Args:
  - uint32_t: The new packed os tag and version.
  - uint32_t: The new packes app tag and version.
  - uint8_t: Update the OS tag, if 0 then the new OS tag is ignored and the
    current one stored is used.
  - uint8_t: Update the APP tag, if 0 then the new APP tag is ingored and
    the current one stored is used.

Returns:
  - uint32_t: An error code.  No error codes are currently possible.
"""
