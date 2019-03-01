"""A packet queue for reordering out of order packets

TODO:
- Add timeout
- replace list with a priority queue
- Add maximum out of order window
"""


class PacketQueue:
    """A queue for reordering out-of-order messages

    Args:
        missing_timeout (int): The maximum time to wait for a missing packet
            without triggering a timeout error
        callback (callable): A callback function that should be called for
            each received message with the signature:
            callback(*args) where args is the list passed to receive
        reorder (bool): Whether this queue should worry about the sequence
            number of packets received since this is a connection oriented
            channel or if each packet is independent and sequence numbers
            should not be checked.  True means sequence numbers are checked
            and packets are reordered.

    """
    def __init__(self, missing_timeout, callback, reorder=True):
        self._out_of_order = []
        self._next_expected = None
        self._callback = callback
        self._reorder = reorder
        self._missing_timeout = missing_timeout

    def receive(self, sequence, args):
        """Receive one packet

        If the sequence number is one we've already seen before, it is dropped.

        If it is not the next expected sequence number, it is put into the
        _out_of_order queue to be processed once the holes in sequence number
        are filled in.

        Args:
            sequence (int): The sequence number of the received packet
            args (list): The list of packet contents that will be passed to callback
                as callback(*args)
        """

        # If we are told to ignore sequence numbers, just pass the packet on
        if not self._reorder:
            self._callback(*args)
            return

        # If this packet is in the past, drop it
        if self._next_expected is not None and sequence < self._next_expected:
            print("Dropping out of order packet, seq=%d" % sequence)
            return

        self._out_of_order.append((sequence, args))
        self._out_of_order.sort(key=lambda x: x[0])

        # If we have received packets, attempt to process them in order
        while len(self._out_of_order) > 0:
            seq, args = self._out_of_order[0]

            if self._next_expected is not None and seq != self._next_expected:
                return

            self._callback(*args)
            self._out_of_order.pop(0)
            self._next_expected = seq+1

    def reset(self):
        """Reset the expected next sequence number
        """

        self._next_expected = None
