import time


class TimeoutInterval:
    """A simple timer that tells you when an interval has expired

    You can check if the timeout is expired by using the expired
    property.  This class attempts to work around issues on devices
    whose time may not be properly synchronized by looking for
    large jumps backwards in time and resetting the interval.

    The net result is that you will have a TimeoutInterval that
    does not go forever when someone sets the time into the past
    but also may not be exactly the interval you set.

    Args:
        timeout (float): The number of seconds from now that the
            timeout should expire.
    """

    def __init__(self, timeout):
        self.start = time.time()
        self.end = self.start + timeout
        self.length = timeout
        self._expired_latch = False

    def _check_time_backwards(self):
        """Make sure a clock reset didn't cause time to go backwards
        """

        now = time.time()

        if now < self.start:
            self.start = now
            self.end = self.start + self.length

    @property
    def expired(self):
        """Boolean property if this timeout has expired
        """
        if self._expired_latch:
            return True

        self._check_time_backwards()

        if time.time() > self.end:
            self._expired_latch = True
            return True

        return False
