"""Configuration information for iotile-ext-cloud."""

import getpass
import urllib3
from iotile.core.dev.registry import ComponentRegistry
from iotile.cloud.cloud import IOTileCloud
from iotile.core.utilities.typedargs import param
from iotile.core.exceptions import ArgumentError
from iotile_cloud.api.connection import Api


@param("username", "string", desc="IOTile cloud username")
@param("password", "string", desc="IOTile cloud password")
def link_cloud(self, username=None, password=None, device_id=None):
    """Create and store a token for interacting with the IOTile Cloud API.

    You will need to call link_cloud once for each virtualenv that
    you create and want to use with any api calls that touch iotile cloud.

    Note that this method is called on a ConfigManager instance

    If you do not pass your username or password it will be prompted from
    you securely on stdin.

    If you are logging in for a user, the token will expire periodically and you
    will have to relogin.

    If you pass a device_id, you can obtain a limited token for that device
    that will never expire, assuming you have access to that device.

    Args:
        username (string): Your iotile.cloud username.  This is prompted
            from stdin if not provided.
        password (string): Your iotile.cloud password.  This is prompted
            from stdin if not provided.
        device_id (int): Optional device id to obtain permanent credentials
            for a device.
    """

    reg = ComponentRegistry()

    domain = self.get('cloud:server')
    verify_server_cert = self.get('cloud:verify-server')

    if username is None:
        prompt_str = "Please enter your IOTile.cloud email: "

        username = input(prompt_str)

    if password is None:
        prompt_str = "Please enter your IOTile.cloud password: "

        password = getpass.getpass(prompt_str)

    if not verify_server_cert:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    cloud = Api(domain=domain, verify=verify_server_cert)
    ok_resp = cloud.login(email=username, password=password)
    if not ok_resp:
        raise ArgumentError("Could not login to iotile.cloud as user %s" % username)

    reg.set_config('arch:cloud_user', cloud.username)
    reg.set_config('arch:cloud_token', cloud.token)
    reg.set_config('arch:cloud_token_type', cloud.token_type)

    if device_id is not None:
        cloud = IOTileCloud()
        cloud.impersonate_device(device_id)


def get_variables():
    """Get a dictionary of configuration variables."""

    prefix = "cloud"

    conf_vars = []
    conf_vars.append(["server", "string", "The domain name to talk to for iotile.cloud operations (including https:// prefix)", 'https://iotile.cloud'])
    conf_vars.append(["verify-server", "bool", "Verify the TLS certificate of the cloud server", "true"])

    return prefix, conf_vars
