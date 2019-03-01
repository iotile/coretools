"""
"""


class TopicSequencer:
    """Keeps track of a packet sequence number for multiple topics

    This class allows you send sequentially numbered messages on each
    MQTT topic to make sure they are received in order by clients
    subscribed to each topic.

    """
    def __init__(self):
        self.topics = {}

    def next_id(self, channel):
        """Get the next sequence number for a named channel or topic

        If channel has not been sent to next_id before, 0 is returned
        otherwise next_id returns the last id returned + 1.

        Args:
            channel (string): The name of the channel to get a sequential
                id for.

        Returns:
            int: The next id for this channel
        """

        if channel not in self.topics:
            self.topics[channel] = 0
            return 0

        self.topics[channel] += 1
        return self.topics[channel]

    def reset(self):
        """Reset the packet id in each topic
        """

        self.topics = {}
