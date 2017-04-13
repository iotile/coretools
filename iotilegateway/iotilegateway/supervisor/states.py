"""All possible states that a service can be in."""

from iotile.core.exceptions import ArgumentError
from monotonic import monotonic

NOT_STARTED = 0
RUNNING = 1
DEGRADED = 2
STOPPED = 3
UNKNOWN = 4

KNOWN_STATES = {
    NOT_STARTED: 'Not Started',
    RUNNING: 'Running',
    STOPPED: 'Stopped',
    UNKNOWN: 'Unknown'
}


class ServiceState(object):
    """A simple object for holding the current state of a service."""

    def __init__(self, short_name, long_name, preregistered, int_id=None):
        """Constructor.

        Args:
            short_name (string): A unique short name for the service
            long_name (string): A user friendly name for the service
            preregistered (bool): Whether this is an expected preregistered
                service
            int_id (int): An internal numeric id for this service
        """

        self.short_name = short_name
        self.long_name = long_name
        self.preregistered = preregistered
        self.last_heartbeat = monotonic()
        self.num_heartbeats = 0
        self.id = int_id
        self._state = UNKNOWN

    @property
    def string_state(self):
        """A string for the curent state."""
        return KNOWN_STATES[self._state]

    @property
    def state(self):
        """The current numeric service state."""
        return self._state

    @property
    def heartbeat_age(self):
        """The time in seconds since the last heartbeat."""
        return monotonic() - self.last_heartbeat

    @state.setter
    def state(self, new_state):
        if new_state not in KNOWN_STATES:
            raise ArgumentError("Unknown service state", state=new_state)

        self._state = new_state

    def heartbeat(self):
        """Record a heartbeat for this service."""

        self.last_heartbeat = monotonic()
        self.num_heartbeats += 1
