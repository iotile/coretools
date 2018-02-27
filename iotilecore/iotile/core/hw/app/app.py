"""Base class for all IOtile Apps."""


class IOTileApp(object):
    """Base class for all IOTile Apps.

    An IOTile App is a class that represents all of the externally visible
    functionality of an IOTile device.  It is typically a subset of what is
    exposed on the individual tiles that make up the iotile device with a
    higher level API.  For example, there may be a shipping tracker IOTile
    device that has an accelerometer and an environmental tile.  The proxy
    objects for those tiles will expose a lot of functionality related to
    acceleration and environmental readings but nothing related to tracking
    a shipment.

    An IOTile App ties together the behavior of all of its underlying tiles.

    IOTile Apps are matched with devices using the device's app tag and version
    which is a number that unique identifies the app running on the device and
    a major.minor version number.

    All IOTile Apps are required to implement a MatchInfo module function if
    they support automatic matching with a device.  The MatchInfo function
    should return a list of (tag, SemanticVersionRange, quality) tuples for each
    app tag they should match with.  The quality value is a floating point
    number between 0 and 100, inclusive, where higher quality matches take
    priority over lower quality matches.  A good default choice is 50.

    Args:
        hw (HardwareManager): A HardwareManager instance connected to a
            matching device.
        app_info (tuple): The app_tag and version of the device we are
            connected to.
        os_info (tuple): The os_tag and version of the device we are
            connected to.
        device_id (int): The UUID of the device that we are connected to.
    """

    def __init__(self, hw, app_info, os_info, device_id):
        self._hw = hw
        self._app_tag = app_info[0]
        self._app_version = app_info[1]
        self._os_tag = os_info[0]
        self._os_version = os_info[1]
        self._device_id = device_id

    @classmethod
    def MatchInfo(cls):
        """Return a list of matching app tag and versions.

        This method must be overriden by all subclasses to return
        their matching information if they want to support automatically
        matching with a device by app_tag.

        Returns:
            list of (int, SemanticVersionRange, float) tuples: A tuple with
                the app_tag and matching version range for all app tags that
                this IOTileApp should match with.  The third float is a
                quality number that will be used to break ties when more than
                one app matches a given device.  Higher is better and the
                value should be in the range [0, 100].
        """

        return []

    @classmethod
    def AppName(cls):
        """A unqiue name for this app so that it can be loaded by name.

        Returns:
            str: The unique name for this app module.
        """

        raise NotImplementedError()
