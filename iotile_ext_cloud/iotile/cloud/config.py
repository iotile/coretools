import getpass

from iotile.core.dev.registry import ComponentRegistry
from iotile.core.utilities.typedargs import param
from iotile.core.exceptions import ArgumentError
from iotile_cloud.api.connection import Api


@param("username", "string", desc="IOTile cloud username")
def link_cloud(self, username=None):
    """Create and store a token for interacting with the IOTile Cloud API

    You will need to call link_cloud once for each virtualenv that
    you create and want to use with any api calls that touch iotile cloud.

    Periodically the token may expire and you will have to relogin.
    """

    reg = ComponentRegistry()

    if username is None:
        username = raw_input("Please enter your iotile.cloud username: ")

    passwd = getpass.getpass('Please enter the iotile.cloud password for %s: ' % username)

    c = Api()
    ok = c.login(email=username, password=passwd)
    if not ok:
        raise ArgumentError("Could not login to iotile.cloud as user %s" % username)

    reg.set_config('arch:cloud_user', username)
    reg.set_config('arch:cloud_token', c.token)
