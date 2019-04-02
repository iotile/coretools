"""Exceptions specific to the websockets subpackage."""

class ServerCommandError(Exception):
    """An internal exception used to signal failure be a command handler.

    This exception communicates from a command handler to
    AsyncValidatingWSServer that the command failed and triggers an
    error response.

    Args:
        command (str): The name of the command that failed.
        reason (str): The reason the command failed.
    """

    def __init__(self, command, reason):
        super(ServerCommandError, self).__init__()

        self.command = command
        self.reason = reason
