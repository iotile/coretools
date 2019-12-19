"""All generation and parsing routines related to iotile device advertisements.

BLE-capable IOTile devices periodically send out advertising packets.

The format of these packets has evolved over time but generally contains the
following information:
 - the device's UUID that allows connecting to the device by UUID.
 - flags and information about the device that are generally important to collect
   without first connecting.
 - any broadcast reports that the device wishes to communicate.
 - a unique identifying GATT Service UUID to permit identifying the device
   as an IOTile compatible device.

There are currently two supported versions of the IOTile advertising format:
v1 and v2.

V1 is an older format and splits the information sent between the advertisement
(device uuid and iotile service) and scan response (any broadcast reports being sent).
This meant that you needed to have BLE Active Scan enabled on your host controller
in order to receive broadcast reports.  This is undesireable for a number of reasons
so the V2 packet format was created.

V2 advertisements are the current IOTile standard.  They include the following
enhancements over the older v1 format:

 - all information is conveyed in a single 31-bytes advertisement packet so there
   is no need for active scanning.
 - it is possible to cryptographically sign the advertisement and encrypt any
   included broadcast reports to prevent unauthorized users from reading broadcast
   data.
"""

from .generation import generate_v1_advertisement, generate_v2_advertisement
