"""Configuration information for iotile-ext-cloud."""

import getpass

from iotile.core.dev.registry import ComponentRegistry
from iotile.core.utilities.typedargs import param
from iotile.core.exceptions import ArgumentError
from iotile_cloud.api.connection import Api


@param("username", "string", desc="IOTile cloud username")
@param("password", "string", desc="IOTile cloud password")
def link_cloud(self, username=None, password=None):
    """Create and store a token for interacting with the IOTile Cloud API.

    You will need to call link_cloud once for each virtualenv that
    you create and want to use with any api calls that touch iotile cloud.

    Note that this method is called on a ConfigManager instance

    If you do not pass your username or password it will be prompted from
    you securely on stdin.

    Periodically the token may expire and you will have to relogin.

    Args:
        username (string): Your iotile.cloud username.  This is prompted
            from stdin if not provided.
        password (string): Your iotile.cloud password.  This is prompted
            from stdin if not provided.
    """

    reg = ComponentRegistry()

    domain = self.get('cloud:server')

    if username is None:
        username = raw_input("Please enter your iotile.cloud username: ")

    if password is None:
        password = getpass.getpass('Please enter the iotile.cloud password for %s: ' % username)

    cloud = Api(domain=domain)
    ok_resp = cloud.login(email=username, password=password)
    if not ok_resp:
        raise ArgumentError("Could not login to iotile.cloud as user %s" % username)

    reg.set_config('arch:cloud_user', cloud.username)
    reg.set_config('arch:cloud_token', cloud.token)


def get_variables():
    """Get a dictionary of configuration variables."""

    prefix = "cloud"

    conf_vars = []
    conf_vars.append(["server", "string", "The domain name to talk to for iotile.cloud operations (including https:// prefix)", 'https://iotile.cloud'])

    return prefix, conf_vars
