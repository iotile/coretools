"""A class that dispatches messages to handlers based on their schema."""
from iotile.core.exceptions import ArgumentError


class ValidatingDispatcher(object):
    """An object that dispatches messages to handlers based on their schema."""

    def __init__(self):
        self.validators = []

    def add_message_type(self, validator, callback):
        """Add a message type that should trigger a callback.

        Each validator must be unique, in that a message will
        be dispatched to the first callback whose validator
        matches the message.

        Args:
            validator (Verifier): A schema verifier that will
                validate a received message uniquely
            callback (callable): The function that should be called
                when a message that matches validator is received.
        """

        self.validators.append((validator, callback))

    def dispatch(self, message):
        """Dispatch a message to a callback based on its schema.

        Args:
            message (dict): The message to dispatch
        """

        for validator, callback in self.validators:
            if not validator.matches(message):
                continue

            callback(message)
            return

        raise ArgumentError("No handler was registered for message", message=message)
