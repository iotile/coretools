"""Shared utility functions."""

import serial
import serial.tools.list_ports
from iotile.core.exceptions import ExternalError

_BAUD_RATE = 230400

def _find_bled112_devices(logger):
    found_devs = []

    # Look for BLED112 dongles on this computer and start an instance on each one
    for port in serial.tools.list_ports.comports():
        if not hasattr(port, 'pid') or not hasattr(port, 'vid'):
            continue

        # Check if the device matches the BLED112's PID/VID combination
        if port.pid == 1 and port.vid == 9304:
            logger.debug("Found BLED112 device at %s", port.device)
            found_devs.append(port.device)

    return found_devs


def _find_available_bled112(logger):
    devices = _find_bled112_devices(logger)
    if len(devices) == 0:
        raise ExternalError("Could not find any BLED112 adapters connected to this computer")

    for port in devices:
        try:
            dev = serial.Serial(port, _BAUD_RATE, timeout=0.01, rtscts=True, exclusive=True)
            logger.info("Using first available BLED112 adapter at %s", port)
            return dev
        except serial.serialutil.SerialException:
            logger.debug("Can't use BLED112 device %s because it's locked", port)

    raise ExternalError("There were %d BLED112 adapters but all were in use." % len(devices))


def open_bled112(port, logger):
    """Open a BLED112 adapter either by name or the first available."""

    if port is not None and port != '<auto>':
        logger.info("Using BLED112 adapter at %s", port)
        return serial.Serial(port, _BAUD_RATE, timeout=0.01, rtscts=True, exclusive=True)

    return _find_available_bled112(logger)
