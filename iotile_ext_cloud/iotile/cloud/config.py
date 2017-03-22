import getpass

from iotile.core.dev.registry import ComponentRegistry
from iotile.core.utilities.typedargs import param
from iotile.core.exceptions import ArgumentError
from iotile_cloud.api.connection import Api


@param("username", "string", desc="IOTile cloud username")
@param("password", "string", desc="IOTile cloud password")
def link_cloud(self, username=None, password=None):
    """Create and store a token for interacting with the IOTile Cloud API

    You will need to call link_cloud once for each virtualenv that
    you create and want to use with any api calls that touch iotile cloud.

    If you do not pass your username or password it will be prompted from
    you securely on stdin.

    Periodically the token may expire and you will have to relogin.
    """

    reg = ComponentRegistry()

    if username is None:
        username = raw_input("Please enter your iotile.cloud username: ")

    if password is None:
        password = getpass.getpass('Please enter the iotile.cloud password for %s: ' % username)

    c = Api()
    ok = c.login(email=username, password=password)
    if not ok:
        raise ArgumentError("Could not login to iotile.cloud as user %s" % username)

    reg.set_config('arch:cloud_user', c.username)
    reg.set_config('arch:cloud_token', c.token)
