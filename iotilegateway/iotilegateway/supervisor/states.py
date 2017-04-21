"""All possible states that a service can be in."""

from iotile.core.exceptions import ArgumentError
from monotonic import monotonic
from collections import deque
from command_formats import MessagePayload

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

    def __init__(self, level, message, message_id, timestamp=None, now_reference=None):
        """Constructor.

        Args:
            level (int): The message importance
            message (string): The message contents
            message_id (int): A unique id for the message
            timestamp (float): An optional monotonic value in seconds for when the message was created
            now_reference (float): If timestamp is not relative to monotonic() as called from this
                module then this should be now() as seen by whoever created the timestamp.
        """

        self.level = level
        self.message = message
        self.count = 1
        self.id = message_id

        if timestamp is None:
            self.created = monotonic()
        elif now_reference is None:
            self.created = timestamp
        else:
            # Figure out the age of the timestamp relative to the now reference from the creator
            # and subtract that age from now for us to convert the timestamp into our frame of
            # reference.
            now = monotonic()
            adj = now - now_reference
            self.created = timestamp + adj

            # Make sure we never create times in the future so that age below is always nonnegative
            if self.created > now:
                self.created = now

    @classmethod
    def FromDictionary(cls, msg_dict):
        """Create from a dictionary with kv pairs.

        Args:
            msg_dict (dict): A dictionary with information as created by to_dict()

        Returns:
            ServiceMessage: the converted message
        """

        MessagePayload.verify(msg_dict)

        level = msg_dict.get('level')
        msg = msg_dict.get('message')
        now = msg_dict.get('now_time')
        created = msg_dict.get('created_time')
        count = msg_dict.get('count', 1)
        msg_id = msg_dict.get('id', 0)

        new_msg = ServiceMessage(level, msg, msg_id, created, now)
        if count > 1:
            new_msg.count = count

        return new_msg

    def to_dict(self):
        """Create a dictionary with the information in this message.

        Returns:
            dict: The dictionary with information
        """

        msg_dict = {}
        msg_dict['level'] = self.level
        msg_dict['message'] = self.message
        msg_dict['now_time'] = monotonic()
        msg_dict['created_time'] = self.created
        msg_dict['id'] = self.id
        msg_dict['count'] = self.count

        return msg_dict

    @property
    def age(self):
        """Return the age of this message in seconds.

        Returns:
            float: the age in seconds
        """

        return monotonic() - self.created


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
        self.headline = None
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

    def post_message(self, level, message, count=1, timestamp=None, now_reference=None):
        """Post a new message for service.

        Args:
            level (int): The level of the message (info, warning, error)
            message (string): The message contents
            count (int): The number of times the message has been repeated
            timestamp (float): An optional monotonic value in seconds for when the message was created
            now_reference (float): If timestamp is not relative to monotonic() as called from this
                module then this should be now() as seen by whoever created the timestamp.
        """

        if len(self.messages) > 0 and self.messages[-1].message == message:
            self.messages[-1].count += 1
        else:
            msg_object = ServiceMessage(level, message, self._last_message_id, timestamp, now_reference)
            msg_object.count = count
            self.messages.append(msg_object)
            self._last_message_id += 1

    def set_headline(self, level, message, timestamp=None, now_reference=None):
        """Set the persistent headline message for this service.

        Args:
            level (int): The level of the message (info, warning, error)
            message (string): The message contents
            timestamp (float): An optional monotonic value in seconds for when the message was created
            now_reference (float): If timestamp is not relative to monotonic() as called from this
                module then this should be now() as seen by whoever created the timestamp.
        """

        if self.headline is not None and self.headline.message == message:
            self.headline.created = monotonic()
            self.headline.count += 1
            return

        msg_object = ServiceMessage(level, message, self._last_message_id, timestamp, now_reference)
        self.headline = msg_object
        self._last_message_id += 1

    def heartbeat(self):
        """Record a heartbeat for this service."""

        self.last_heartbeat = monotonic()
        self.num_heartbeats += 1
