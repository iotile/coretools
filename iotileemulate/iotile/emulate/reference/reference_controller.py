"""A reference implementation of the iotile controller that allows update verification."""

import logging
import asyncio
from iotile.core.hw.virtual import tile_rpc
from iotile.core.hw.exceptions import TileNotFoundError
from iotile.core.hw.reports import IOTileReading
from iotile.core.exceptions import ArgumentError
from iotile.sg.model import DeviceModel
from iotile.sg.parser import SensorGraphFileParser
from iotile.sg.optimizer import SensorGraphOptimizer
from ..virtual import EmulatedTile
from ..constants import rpcs, Error

from .controller_features import (RawSensorLogMixin, RemoteBridgeMixin,
                                  TileManagerMixin, ConfigDatabaseMixin, SensorGraphMixin,
                                  StreamingSubsystemMixin, ClockManagerMixin)


class ReferenceController(RawSensorLogMixin, RemoteBridgeMixin,
                          TileManagerMixin, ConfigDatabaseMixin,
                          SensorGraphMixin, StreamingSubsystemMixin,
                          ClockManagerMixin, EmulatedTile):
    """A reference iotile controller implementation.

    This tile implements the major behavior of an IOTile controller including
    setting and inspecting sensorgraphs as well as setting and inspecting user
    keys and app/os tags.  The default reference implementation does not do
    anything with set data except expose it on public properties so that we
    can verify what was done to the device.

    Args:
        address (int): The address of this tile in the VirtualIOTIleDevice
            that contains it
        args (dict): The arguments to use to create this tile.  The currently supported
            arguments are:
                name (str): The 6 character name that should be returned when this
                    tile is asked for its status to allow matching it with a proxy
                    object.
        device (TileBasedVirtualDevice) : optional, device on which this tile is running
    """

    STATE_NAME = "reference_controller"
    STATE_VERSION = "0.1.0"

    def __init__(self, address, args, device=None):
        self.name = args.get('name', 'refcn1')
        self._device = device
        self._logger = logging.getLogger(__name__)
        self._post_config_subsystems = []

        if not isinstance(self.name, bytes):
            self.name = self.name.encode('utf-8')

        model = DeviceModel()

        EmulatedTile.__init__(self, address, device)

        # Initialize all of the controller subsystems
        ClockManagerMixin.__init__(self, device.emulator, has_rtc=False) #FIXME: Load the controller model info to get whether it has an RTC
        ConfigDatabaseMixin.__init__(self, 4096, 4096)  #FIXME: Load the controller model info to get its memory map
        TileManagerMixin.__init__(self, device.emulator)
        RemoteBridgeMixin.__init__(self, device.emulator)
        RawSensorLogMixin.__init__(self, device.emulator, model)
        StreamingSubsystemMixin.__init__(self, device.emulator, basic=True)
        SensorGraphMixin.__init__(self, device.emulator, self.sensor_log, self.stream_manager, model=model)

        # Establish required post-init linkages between subsystems
        self.clock_manager.graph_input = self.sensor_graph.process_input
        self.sensor_graph.get_timestamp = self.clock_manager.get_time
        self.stream_manager.get_timestamp = self.clock_manager.get_time
        self.stream_manager.get_uptime = lambda: self.clock_manager.get_time(False)

        self.app_info = (0, "0.0")
        self.os_info = (0, "0.0")

        self.register_scenario('load_sgf', self.load_sgf)

    def _handle_reset(self):
        """Reset this controller tile.

        This process will call _handle_reset() for all of the controller
        subsystem mixins in order to make sure they all return to their proper
        reset state.

        It will then reset all of the peripheral tiles to emulate the behavior
        of a physical POD where the controller tile cuts power to all
        peripheral tiles on reset for a clean boot.

        This will clear all subsystems of this controller to their reset
        states.

        The order of these calls is important to guarantee that everything is
        in the correct state before resetting the next subsystem.

        The behavior of this function is different depending on whether
        deferred is True or False.  If it's true, this function will only
        clear the config database and then queue all of the config streaming
        rpcs to itself to load in all of our config variables.  Once these
        have been sent, it will reset the rest of the controller subsystems.
        """

        self._logger.info("Resetting controller")
        self._device.reset_count += 1

        super(ReferenceController, self)._handle_reset()

        # Load in all default values into our config variables before streaming
        # updated data into them.
        self.reset_config_variables()

    async def _reset_vector(self):
        """Initialize the controller's subsystems inside the emulation thread."""

        # Send ourselves all of our config variable assignments
        config_rpcs = self.config_database.stream_matching(8, self.name)
        for rpc in config_rpcs:
            await self._device.emulator.await_rpc(*rpc)

        config_assignments = self.latch_config_variables()
        self._logger.info("Latched config variables at reset for controller: %s", config_assignments)

        for system in self._post_config_subsystems:
            try:
                system.clear_to_reset(config_assignments)
                await asyncio.wait_for(system.initialize(), timeout=2.0)
            except:
                self._logger.exception("Error initializing %s", system)
                raise

        self._logger.info("Finished clearing controller to reset condition")

        # Now reset all of the tiles
        for address, _ in self._device.iter_tiles(include_controller=False):
            self._logger.info("Sending reset signal to tile at address %d", address)

            try:
                await self._device.emulator.await_rpc(address, rpcs.RESET)
            except TileNotFoundError:
                pass
            except:
                self._logger.exception("Error sending reset signal to tile at address %d", address)
                raise

        self.initialized.set()

    def dump_state(self):
        """Dump the current state of this emulated object as a dictionary.

        Returns:
            dict: The current state of the object that could be passed to load_state.
        """

        superstate = super(ReferenceController, self).dump_state()

        superstate.update({
            'state_name': self.STATE_NAME,
            'state_version': self.STATE_VERSION,
            'app_info': self.app_info,
            'os_info': self.os_info,

            # Dump all of the subsystems
            'remote_bridge': self.remote_bridge.dump(),
            'tile_manager': self.tile_manager.dump(),
            'config_database': self.config_database.dump(),
            'sensor_log': self.sensor_log.dump()
        })

        return superstate

    def restore_state(self, state):
        """Restore the current state of this emulated object.

        Args:
            state (dict): A previously dumped state produced by dump_state.
        """

        super(ReferenceController, self).restore_state(state)

        state_name = state.get('state_name')
        state_version = state.get('state_version')

        if state_name != self.STATE_NAME or state_version != self.STATE_VERSION:
            raise ArgumentError("Invalid emulated device state name or version", found=(state_name, state_version),
                                expected=(self.STATE_NAME, self.STATE_VERSION))

        self.app_info = state.get('app_info', (0, "0.0"))
        self.os_info = state.get('os_info', (0, "0.0"))

        # Notify all subsystems of our intent to restore in case they need to prepare
        self.sensor_log.prepare_for_restore()

        # Restore all of the subsystems
        self.remote_bridge.restore(state.get('remote_bridge', {}))
        self.tile_manager.restore(state.get('tile_manager', {}))
        self.config_database.restore(state.get('config_database', {}))
        self.sensor_log.restore(state.get('sensor_log', {}))

    @tile_rpc(*rpcs.HARDWARE_VERSION)
    def hardware_version(self):
        """Get a hardware identification string."""

        hardware_string = self.hardware_string

        if not isinstance(hardware_string, bytes):
            hardware_string = self.hardware_string.encode('utf-8')

        if len(hardware_string) > 10:
            self._logger.warn("Truncating hardware string that was longer than 10 bytes: %s", self.hardware_string)

        if len(hardware_string) < 10:
            hardware_string += b'\0'*(10 - len(hardware_string))

        return [hardware_string]

    @tile_rpc(0x1008, "", "L8xLL")
    def controller_info(self):
        """Get the controller UUID, app tag and os tag."""

        return [self._device.iotile_id, _pack_version(*self.os_info), _pack_version(*self.app_info)]

    @tile_rpc(*rpcs.SET_OS_APP_TAG)
    def set_app_os_tag(self, os_tag, app_tag, update_os, update_app):
        """Update the app and/or os tags."""

        update_os = bool(update_os)
        update_app = bool(update_app)

        if update_os:
            self.os_info = _unpack_version(os_tag)

        if update_app:
            self.app_info = _unpack_version(app_tag)

        return [Error.NO_ERROR]

    # FIXME: Move this to the background thread
    def load_sgf(self, sgf_data):
        """Load, persist a sensor_graph file.

        The data passed in `sgf_data` can either be a path or the already
        loaded sgf lines as a string.  It is determined to be sgf lines if
        there is a '\n' character in the data, otherwise it is interpreted as
        a path.

        Note that this scenario just loads the sensor_graph directly into the
        persisted sensor_graph inside the device.  You will still need to
        reset the device for the sensor_graph to enabled and run.

        Args:
            sgf_data (str): Either the path to an sgf file or its contents
                as a string.
        """

        if '\n' not in sgf_data:
            with open(sgf_data, "r") as infile:
                sgf_data = infile.read()

        model = DeviceModel()

        parser = SensorGraphFileParser()
        parser.parse_file(data=sgf_data)

        parser.compile(model)
        opt = SensorGraphOptimizer()
        opt.optimize(parser.sensor_graph, model=model)

        sensor_graph = parser.sensor_graph
        self._logger.info("Loading sensor_graph with %d nodes, %d streamers and %d configs",
                          len(sensor_graph.nodes), len(sensor_graph.streamers), len(sensor_graph.config_database))

        # Directly load the sensor_graph into our persisted storage
        self.sensor_graph.persisted_nodes = sensor_graph.dump_nodes()
        self.sensor_graph.persisted_streamers = sensor_graph.dump_streamers()

        self.sensor_graph.persisted_constants = []
        for stream, value in sorted(sensor_graph.constant_database.items(), key=lambda x: x[0].encode()):
            reading = IOTileReading(stream.encode(), 0, value)
            self.sensor_graph.persisted_constants.append((stream, reading))

        self.sensor_graph.persisted_exists = True

        # Clear all config variables and load in those from this sgf file
        self.config_database.clear()

        for slot in sorted(sensor_graph.config_database, key=lambda x: x.encode()):
            for conf_var, (conf_type, conf_val) in sorted(sensor_graph.config_database[slot].items()):
                self.config_database.add_direct(slot, conf_var, conf_type, conf_val)

        # If we have an app tag and version set program them in
        app_tag = sensor_graph.metadata_database.get('app_tag')
        app_version = sensor_graph.metadata_database.get('app_version')

        if app_tag is not None:
            if app_version is None:
                app_version = "0.0"

            self.app_info = (app_tag, app_version)


def _pack_version(tag, version):
    if tag >= (1 << 20):
        raise ArgumentError("The tag number is too high.  It must fit in 20-bits", max_tag=1 << 20, tag=tag)

    if "." not in version:
        raise ArgumentError("You must pass a version number in X.Y format", version=version)

    major, _, minor = version.partition('.')
    try:
        major = int(major)
        minor = int(minor)
    except ValueError:
        raise ArgumentError("Unable to convert version string into major and minor version numbers", version=version)

    if major < 0 or minor < 0 or major >= (1 << 6) or minor >= (1 << 6):
        raise ArgumentError("Invalid version numbers that must be in the range [0, 63]", major=major, minor=minor, version_string=version)

    version_number = (major << 6) | minor
    combined_tag = (version_number << 20) | tag
    return combined_tag


def _unpack_version(tag_data):
    """Parse a packed version info struct into tag and major.minor version.

    The tag and version are parsed out according to 20 bits for tag and
    6 bits each for major and minor.  The more interesting part is the
    blacklisting performed for tags that are known to be untrustworthy.

    In particular, the following applies to tags.

    - tags < 1024 are reserved for development and have only locally defined
      meaning.  They are not for use in production.
    - tags in [1024, 2048) are production tags but were used inconsistently
      in the early days of Arch and hence cannot be trusted to correspond with
      an actual device model.
    - tags >= 2048 are reserved for supported production device variants.
    - the tag and version 0 (0.0) is reserved for an unknown wildcard that
      does not convey any information except that the tag and version are
      not known.
    """

    tag = tag_data & ((1 << 20) - 1)

    version_data = tag_data >> 20
    major = (version_data >> 6) & ((1 << 6) - 1)
    minor = (version_data >> 0) & ((1 << 6) - 1)

    return (tag, "{}.{}".format(major, minor))
