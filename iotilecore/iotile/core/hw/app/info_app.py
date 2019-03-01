from typedargs.annotate import context
from .app import IOTileApp


@context("InfoApp")
class InfoApp(IOTileApp):
    """A Basic IOTile App that can print information about the connected device."""

    @classmethod
    def AppName(cls):
        """A unique name for this app so that it can be loaded by name.

        Returns:
            str: The unique name for this app module.
        """

        return 'device_info'
