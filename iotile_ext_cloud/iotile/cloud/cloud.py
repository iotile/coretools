"""Routines for interacting with IOTile cloud from the command line
"""

from builtins import input
from io import BytesIO
import getpass
import datetime
import requests
from dateutil.tz import tzutc
import dateutil.parser
from collections import namedtuple

from iotile_cloud.api.connection import Api
from iotile_cloud.api.exceptions import RestHttpBaseException, HttpNotFoundError
from iotile.core.dev.registry import ComponentRegistry
from iotile.core.dev.config import ConfigManager
from iotile.core.hw.reports import IndividualReadingReport, SignedListReport, FlexibleDictionaryReport
from iotile.core.exceptions import ArgumentError, ExternalError, DataError
from iotile.core.utilities.typedargs import context, param, return_type, annotated, type_system
from .utilities import device_id_to_slug, fleet_id_to_slug

Acknowledgement = namedtuple("Acknowledgement", ["index", "ack", "selector"])

@context("IOTileCloud")
class IOTileCloud(object):
    """High level routines for interacting with IOTile cloud.

    Normally, you can create one of these objects with no arguments
    and the iotile.cloud server and authentication details will
    be pulled from the ComponentRegistry.  However, you can force
    a specific domain by passing the optional domain arguments.

    If there are no stored credentials in ComponentRegistry, the
    user will be prompted for a password on the command line IF
    the session is interactive, otherwise __init__ will fail.

    Args:
        domain (str): Optional server domain.  If not specified,
            the default will be whatever is stored in the registry
        username (str): Optional username to force the user to use
            if they don't have stored credentials
    """

    DEVICE_TOKEN_TYPE = 'a-jwt'

    def __init__(self, domain=None, username=None):
        reg = ComponentRegistry()
        conf = ConfigManager()

        if domain is None:
            domain = conf.get('cloud:server')

        self.api = Api(domain=domain)

        try:
            token = reg.get_config('arch:cloud_token')
            token_type = reg.get_config('arch:cloud_token_type', default='jwt')
            self.api.set_token(token, token_type=token_type)
        except ArgumentError:
            # If we are interactive, try to get the user to login for a single
            # session rather than making them call link_cloud to store a cloud token
            if type_system.interactive:
                if username is None:
                    username = input("Please enter your (%s) username: " % domain)

                password = getpass.getpass('Please enter the (%s) password for %s: ' % (domain, username))
                ok_resp = self.api.login(email=username, password=password)

                if not ok_resp:
                    raise ExternalError("Could not login to %s as user %s" % (domain, username))
            else:
                raise ExternalError("No stored iotile cloud authentication information", suggestion='Call iotile config link_cloud with your iotile cloud username and password')

        self.token = self.api.token
        self.token_type = self.api.token_type

    @property
    def refresh_required(self):
        return self.token_type == 'jwt'

    def _build_streamer_slug(self, device_id, streamer_id):
        idhex = "{:04x}".format(device_id)
        streamer_hex = "{:04x}".format(streamer_id)

        return "t--0000-0000-0000-{}--{}".format(idhex, streamer_hex)

    @param("device_id", "integer", desc="ID of the device that we want information about")
    @return_type("basic_dict")
    def device_info(self, device_id):
        """Query information about a device by its device id
        """

        slug = device_id_to_slug(device_id)

        try:
            dev = self.api.device(slug).get()
        except HttpNotFoundError:
            raise ArgumentError("Device does not exist in cloud database", device_id=device_id, slug=slug)

        return dev

    @param("fleet_id", "integer", desc="Id of the fleet we want to retrieve")
    @return_type("basic_dict")
    def get_fleet(self, fleet_id):
        """ Returns the devices in the given fleet."""

        api = self.api

        slug = fleet_id_to_slug(fleet_id)

        try:
            results = api.fleet(slug).devices.get()
            entries = results.get('results', [])
            return {entry.pop('device'): entry for entry in entries}
        except HttpNotFoundError:
            raise ArgumentError("Fleet does not exist in cloud database", fleet_id=fleet_id, slug=slug)

    @param("device_id", "integer", desc="Id of the device whose fleet we want to retrieve")
    @return_type("basic_dict")
    def get_whitelist(self, device_id):
        """ Returns the whitelist associated with the given device_id if any"""
        api = self.api
        slug = device_id_to_slug(device_id)
        try:
            fleets = api.fleet.get(device=slug)['results']
        except HttpNotFoundError:
            raise ExternalError("Could not find the right URL. Are fleets enabled ?")

        if not fleets:
            # This is to be expected for devices set to take data from all project, or any device.
            raise ExternalError("The device isn't in any network !")

        networks = [self.get_fleet(fleet['id']) for fleet in fleets if fleet.get('is_network', False) is True]
        networks_to_manage = [x for x in networks if x.get(slug, {}).get('is_access_point', False) is True]

        out = {}
        for network in networks_to_manage:
            out.update(network)

        # Remove ourselves from the whitelist that we are supposed to manage
        if slug in out:
            del out[slug]

        if not out:
            raise ExternalError("No device to manage in these fleets !")

        return out

    @param("max_slop", "integer", desc="Optional max time difference value")
    @return_type("bool")
    def check_time(self, max_slop=300):
        """ Check if current system time is consistent with iotile.cloud time"""

        cloud_time = requests.get('https://iotile.cloud/api/v1/server/').json().get('now', None)
        if cloud_time is None:
            raise DataError("No date header returned from iotile.cloud")

        curtime = datetime.datetime.now(tzutc())
        delta = dateutil.parser.parse(cloud_time) - curtime
        delta_secs = delta.total_seconds()

        return abs(delta_secs) < max_slop

    @param("device_id", "integer", desc="ID of the device that we want information about")
    @param("new_sg", "string", desc="The new sensor graph id that we want to load")
    @param("app_tag", "integer", desc="Optional arg to check if the device template on the cloud matches the app_tag")
    def set_sensorgraph(self, device_id, new_sg, app_tag=None):
        """The the cloud's sensor graph id that informs what kind of device this is.

        Is app_tag is passed, verify that the sensorgraph explicitly matches
        the expected app_tag by making another API call.

        Args:
            device_id (int): The id of the device that we want to change the sensorgraph for.
            new_sg (string): Name of a valid sensorgraph that you wish to set the device to
            app_tag (int): Optional. The intended app_tag of the sensorgraph will be set. If the
                app_tag passed into this function does not match the app_tag of the sensorgraph
                in iotile.cloud, raise an error.
        """
        try:
            sg = self.api.sg(new_sg).get()
        except RestHttpBaseException as exc:
            raise ExternalError("Error calling method on iotile.cloud", exception=exc, response=exc.response.status_code)

        if app_tag is not None:
            if sg.get('app_tag', None) != app_tag:
                raise ArgumentError("Cloud sensorgraph record does not match app tag", value=new_sg, cloud_sg_app_tag=sg.get('app_tag', None), app_tag_set=app_tag)

        slug = device_id_to_slug(device_id)
        patch = {'sg': new_sg}

        try:
            self.api.device(slug).patch(patch)
        except RestHttpBaseException as exc:
            if exc.response.status_code == 400:
                raise ArgumentError("Error setting sensor graph, invalid value", value=new_sg, error_code=exc.response.status_code)
            else:
                raise ExternalError("Error calling method on iotile.cloud", exception=exc, response=exc.response.status_code)

    @param("device_id", "integer", desc="ID of the device that we want information about")
    @param("new_template", "string", desc="The new device template that we want to set")
    @param("os_tag", "integer", desc="Optional arg to check if the sensorgraph on the cloud matches the os_tag")
    def set_device_template(self, device_id, new_template, os_tag=None):
        """Sets the device template for the given device in iotile.cloud.

        Is os_tag is passed, verify that the device template explicitly matches
        the expected os_tag by making another API call.
        Args:
            device_id (int): The id of the device that we want to change the device template for.
            new_template (string): Name of a valid device template that you wish to set the device to
            os_tag (int): Optional. If the os_tag passed into this function does not match the
                os_tag of the device_tmplate in iotile.cloud, raise an error.
        """
        try:
            dt = self.api.dt(new_template).get()
        except RestHttpBaseException as exc:
            raise ExternalError("Error calling method on iotile.cloud", exception=exc, response=exc.response.status_code)

        if os_tag is not None:
            if dt.get('os_tag', None) != os_tag:
                raise ArgumentError("Cloud device template record does not match os tag", value=new_template, cloud_sg_os_tag=dt.get('os_tag', None), os_tag_set=os_tag)

        slug = device_id_to_slug(device_id)
        patch = {'template': new_template}

        try:
            self.api.device(slug).patch(patch, staff=1)
        except RestHttpBaseException as exc:
            if exc.response.status_code == 400:
                raise ArgumentError("Error setting device template, invalid value", value=new_template, error_code=exc.response.status_code)
            else:
                raise ExternalError("Error calling method on iotile.cloud", exception=exc, response=exc.response.status_code)

    @param("project_id", "string", desc="Optional ID of the project to download a list of devices from")
    @return_type("list(integer)")
    def device_list(self, project_id=None):
        """Download a list of all device IDs or device IDs that are members for a specific project."""

        if project_id:
            devices = self.api.device.get(project=project_id)
        else:
            devices = self.api.device.get()

        ids = [device['id'] for device in devices['results']]
        return ids

    @param("device_id", "integer", desc="ID of the device that we want to get a permanent token for")
    def impersonate_device(self, device_id):
        """Convert our token to a permanent device token.

        This function is most useful for creating virtual IOTile devices whose access to iotile.cloud
        is based on their device id, not any particular user's account.

        There are a few differences between device tokens and user tokens:
         - Device tokens never expire and don't need to be refreshed
         - Device tokens are more restricted in what they can access in IOTile.cloud than user tokens

        Args:
            device_id (int): The id of the device that we want to get a token for.
        """

        slug = device_id_to_slug(device_id)
        token_type = IOTileCloud.DEVICE_TOKEN_TYPE

        try:
            resp = self.api.device(slug).key.get(type=IOTileCloud.DEVICE_TOKEN_TYPE)
            token = resp['key']
        except RestHttpBaseException as exc:
            raise ExternalError("Error calling method on iotile.cloud", exception=exc, response=exc.response.status_code)

        self.api.set_token(token, token_type=token_type)
        self.token = token
        self.token_type = token_type

        reg = ComponentRegistry()
        reg.set_config('arch:cloud_token', self.token)
        reg.set_config('arch:cloud_token_type', self.token_type)
        reg.set_config('arch:cloud_device', slug)

    @param("device_id", "integer", desc="ID of the device that we want information about")
    @param("clean", "bool", desc="Also clean old stream data for this device")
    def unclaim(self, device_id, clean=True):
        """Unclaim a device that may have previously been claimed."""

        slug = device_id_to_slug(device_id)

        payload = {'clean_streams': clean}

        try:
            self.api.device(slug).unclaim.post(payload)
        except RestHttpBaseException as exc:
            raise ExternalError("Error calling method on iotile.cloud", exception=exc, response=exc.response.status_code)

    def upload_report(self, report):
        """Upload an IOTile report to the cloud.

        This function currently supports uploading the following kinds of
        reports:
            SignedListReport
            FlexibleDictionaryReport

        If you pass an instance of IndividualReadingReport, an exception will
        be thrown because IOTile.cloud does not support receiving individual
        readings.  Those are only for local use.

        The filename of the uploaded report will have an extension set based
        on the type of report that you are uploading.

        Args:
            report (IOTileReport): The report that you want to upload.  This should
                not be an IndividualReadingReport.

        Returns:
            int: The number of new readings that were accepted by the cloud as novel.
        """

        if isinstance(report, IndividualReadingReport):
            raise ArgumentError("You cannot upload IndividualReadingReport objects to iotile.cloud", report=report)

        if isinstance(report, SignedListReport):
            file_ext = ".bin"
        elif isinstance(report, FlexibleDictionaryReport):
            file_ext = ".mp"
        else:
            raise ArgumentError("Unknown report format passed to upload_report", classname=report.__class__.__name__, report=report)

        timestamp = '{}'.format(report.received_time.isoformat())
        payload = {'file': ("report" + file_ext, BytesIO(report.encode()))}

        resource = self.api.streamer.report

        headers = {}
        authorization_str = '{0} {1}'.format(self.token_type, self.token)
        headers['Authorization'] = authorization_str

        resp = requests.post(resource.url(), files=payload, headers=headers, params={'timestamp': timestamp})

        count = resource._process_response(resp)['count']
        return count

    def highest_acknowledged(self, device_id, streamer):
        """Get the highest acknowledged reading for a given streamer.

        Args:
            device_id (int): The device whose streamer we are querying
            streamer (int): The streamer on the device that we want info
                about.

        Returns:
            int: The highest reading id that has been acknowledged by the cloud
        """

        slug = self._build_streamer_slug(device_id, streamer)

        try:
            data = self.api.streamer(slug).get()
        except RestHttpBaseException as exc:
            raise ArgumentError("Could not get information for streamer", device_id=device_id, streamer_id=streamer, slug=slug, err=str(exc))

        if 'last_id' not in data:
            raise ExternalError("Response fom the cloud did not have last_id set", response=data)

        return data['last_id']

    def device_acknowledgements(self, device_id):
        """Get all streamer acknowledgements for a device by its id.

        Args:
            device_id (int): The device we are querying

        Returns:
            list of namedtuples: A list of all acknowledgement values received from the cloud.
                The namedtuples should have index, ack and selector fields pulled from the corresponding
                record in the cloud.
        """

        slug = device_id_to_slug(device_id)

        try:
            data = self.api.streamer().get(device=slug)
        except RestHttpBaseException as exc:
            raise ArgumentError("Could not get information for streamer", device_id=device_id, slug=slug, err=str(exc))

        results = data.get('results', [])

        acknowledgements = []

        for result in results:
            acknowledgement = Acknowledgement(
                result.get("index"),
                result.get("last_id"),
                result.get("selector")
            )

            acknowledgements.append(acknowledgement)

        return acknowledgements

    @annotated
    def refresh_token(self):
        """Attempt to refresh out cloud token with iotile.cloud."""

        if self.token_type != 'jwt':
            raise DataError("Attempting to refresh a token that does not need to be refreshed", token_type=self.token_type)

        conf = ConfigManager()
        domain = conf.get('cloud:server')

        url = '{}/api/v1/auth/api-jwt-refresh/'.format(domain)

        resp = requests.post(url, json={'token': self.token})
        if resp.status_code != 200:
            raise ExternalError("Could not refresh token", error_code=resp.status_code)

        data = resp.json()

        # Save token that we just refreshed to the registry and update our own token
        self.token = data['token']

        reg = ComponentRegistry()
        reg.set_config('arch:cloud_token', self.token)
