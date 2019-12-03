#!/usr/bin/env python
#
#   Copyright 2012 Jonas Berg
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#

"""

.. moduleauthor:: Jonas Berg <pyhys@users.sourceforge.net>

dummy_serial: A dummy/mock implementation of a serial port for testing purposes.

"""

__author__  = 'Jonas Berg'
__email__   = 'pyhys@users.sourceforge.net'
__license__ = 'Apache License, Version 2.0'

import logging
import queue

DEFAULT_TIMEOUT = 5
"""The default timeout value in seconds. Used if not set by the constructor."""


RESPONSE_GENERATOR = None
"""A dictionary of respones from the dummy serial port.

The key is the message (string) sent to the dummy serial port, and the item is the response (string)
from the dummy serial port.

Intended to be monkey-patched in the calling test module.
"""

class Serial:
    """Dummy (mock) serial port for testing purposes.

    Mimics the behavior of a serial port as defined by the `pySerial <http://pyserial.sourceforge.net/>`_ module.

    Args:
        * port:
        * timeout:

    Note:
    As the portname argument not is used properly, only one port on :mod:`dummy_serial` can be used simultaneously.

    """

    def __init__(self, port, baudrate, *_args, **kwargs):
        self._waiting_data = b''
        self._writes = queue.Queue()

        self._is_open = True
        self.port = port  # Serial port name.
        self.initial_port_name = self.port  # Initial name given to the serial port
        self.timeout = kwargs.get('timeout', DEFAULT_TIMEOUT)
        self.baudrate = baudrate

        self._logger = logging.getLogger(__name__)

    def __repr__(self):
        """String representation of the dummy_serial object"""
        return "{0}.{1}<id=0x{2:x}, open={3}>(port={4!r}, timeout={5!r}".format(
            self.__module__,
            self.__class__.__name__,
            id(self),
            self._is_open,
            self.port,
            self.timeout
        )

    def open(self):
        """Open a (previously initialized) port on dummy_serial."""

        if self._is_open:
            raise IOError('Dummy_serial: The port is already open')

        self._is_open = True
        self.port = self.initial_port_name

    def close(self):
        """Close a port on dummy_serial."""

        if not self._is_open:
            raise IOError('Dummy_serial: The port is already closed')

        self._is_open = False
        self.port = None

    def inject(self, data):
        """Inject data asynchronously into the serial port to simulate an event

        Args:
            data (bytes): the data to be injected into the serial port read buffer
        """

        self._writes.put(data)

    def write(self, inputdata):
        """Write to a port on dummy_serial.

        Args:
            inputdata (bytes): data for sending to the port on dummy_serial.
        """

        if not isinstance(inputdata, bytes):
            raise TypeError('The input must be type bytes. Given:' + repr(inputdata))

        if not self._is_open:
            raise IOError('Dummy_serial: Trying to write, but the port is not open. Given:' + repr(inputdata))

        # Look up which data that should be waiting for subsequent read commands
        try:
            response = RESPONSE_GENERATOR(inputdata)
        except:
            self._logger.exception("Error generating response")
            raise

        self._writes.put(response)

    def cancel_read(self):
        """Cancel an ongoing read.

        See pyserial.Serial.cancel_read().  This is a feature in pyserial 3.0
        to allow for stopping a read that is in progress without waiting for
        a timeout to expire.  It is needed in cases where you are using a
        background thread to read from the serial port and need to wake that
        thread up.
        """

        self._writes.put(None)

    def read(self, read_count):
        """Read from a port on dummy_serial.

        The response is dependent on what was written last to the port on dummy_serial,
        and what is defined in the :data:`RESPONSES` dictionary.

        Args:
            read_count (int): For compability with the real function.

        If the response is shorter than read_count, it will sleep for up to timeout.
        If the response is longer than read_count, it will return only read_count bytes.
        """

        if read_count < 0:
            raise IOError('Dummy_serial: The read_count to read must not be negative. Given: {!r}'.format(read_count))

        if not self._is_open:
            raise IOError('Dummy_serial: Trying to read, but the port is not open.')

        while len(self._waiting_data) < read_count:
            try:
                data = self._writes.get(timeout=self.timeout)
                if data is None:
                    break

                self._waiting_data += data
            except queue.Empty:
                break

        return_data = self._waiting_data[:read_count]
        self._waiting_data = self._waiting_data[read_count:]

        return return_data
