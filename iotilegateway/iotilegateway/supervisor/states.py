"""All possible states that a service can be in."""

from iotile.core.exceptions import ArgumentError
from monotonic import monotonic
from collections import deque

# Service states
NOT_STARTED = 0
RUNNING = 1
DEGRADED = 2
STOPPED = 3
UNKNOWN = 4

KNOWN_STATES = {
    NOT_STARTED: 'Not Started',
    RUNNING: 'Running',
    STOPPED: 'Stopped',
    DEGRADED: 'Degraded',
    UNKNOWN: 'Unknown'
}

# Message Levels
INFO_LEVEL = 0
WARNING_LEVEL = 1
ERROR_LEVEL = 2


class ServiceMessage(object):
    """A message received from a service."""

    def __init__(self, level, message, message_id):
        """Constructor.

        Args:
            level (int): The message importance
            message (string): The message contents
            message_id (int): A unique id for the message
        """

        self.level = level
        self.message = message
        self.count = 1
        self.id = message_id


class ServiceState(object):
    """A simple object for holding the current state of a service."""

    def __init__(self, short_name, long_name, preregistered, int_id=None, max_messages=5):
        """Constructor.

        Args:
            short_name (string): A unique short name for the service
            long_name (string): A user friendly name for the service
            preregistered (bool): Whether this is an expected preregistered
                service
            int_id (int): An internal numeric id for this service
            max_messages (int): The maximum number of messages to keep
        """

        self.short_name = short_name
        self.long_name = long_name
        self.preregistered = preregistered
        self.last_heartbeat = monotonic()
        self.num_heartbeats = 0
        self.id = int_id
        self._state = UNKNOWN
        self.messages = deque(maxlen=max_messages)
        self._last_message_id = 0

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

    def get_message(self, message_id):
        """Get a message by its persistent id.

        Args:
            message_id (int): The id of the message that we're looking for
        """

        for message in self.messages:
            if message.id == message_id:
                return message

        raise ArgumentError("Message ID not found", message_id=message_id)

    def post_message(self, level, message):
        """Post a new message for service.

        Args:
            level (int): The level of the message (info, warning, error)
            message (string): The message contents
        """

        if len(self.messages) > 0 and self.messages[-1].message == message:
            self.messages[-1].count += 1
        else:
            msg_object = ServiceMessage(level, message, self._last_message_id)
            self.messages.append(msg_object)
            self._last_message_id += 1

    def heartbeat(self):
        """Record a heartbeat for this service."""

        self.last_heartbeat = monotonic()
        self.num_heartbeats += 1
