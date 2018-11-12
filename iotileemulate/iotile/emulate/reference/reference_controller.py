"""A reference implementation of the iotile controller that allows update verification."""

from __future__ import print_function, absolute_import, unicode_literals
import logging
from iotile.core.hw.virtual import tile_rpc, TileNotFoundError
from iotile.core.exceptions import ArgumentError
from iotile.sg.model import DeviceModel
from ..virtual import EmulatedTile
from ..constants import rpcs

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
        name = args.get('name', 'refcn1')
        self._device = device
        self._logger = logging.getLogger(__name__)
        self._post_config_subsystems = []

        model = DeviceModel()

        EmulatedTile.__init__(self, address, name, device)

        # Initialize all of the controller subsystems
        ClockManagerMixin.__init__(self, has_rtc=False) #FIXME: Load the controller model info to get whether it has an RTC
        ConfigDatabaseMixin.__init__(self, 4096, 4096)  #FIXME: Load the controller model info to get its memory map
        TileManagerMixin.__init__(self)
        RemoteBridgeMixin.__init__(self)
        RawSensorLogMixin.__init__(self, model)
        StreamingSubsystemMixin.__init__(self, basic=True)
        SensorGraphMixin.__init__(self, self.sensor_log, self.stream_manager, model=model)

        # Establish required post-init linkages between subsystems
        self.clock_manager.graph_input = self.sensor_graph.process_input
        self.sensor_graph.get_timestamp = self.clock_manager.get_time
        self.stream_manager.get_timestamp = self.clock_manager.get_time
        self.stream_manager.get_uptime = lambda: self.clock_manager.get_time(False)

        self.app_info = (0, "0.0")
        self.os_info = (0, "0.0")

    def _clear_to_reset_condition(self, deferred=False):
        """Clear all subsystems of this controller to their reset states.

        The order of these calls is important to guarantee that everything
        is in the correct state before resetting the next subsystem.

        The behavior of this function is different depending on whether
        deferred is True or False.  If it's true, this function will only
        clear the config database and then queue all of the config streaming
        rpcs to itself to load in all of our config variables.  Once these
        have been sent, it will reset the rest of the controller subsystems.
        """

        # Load in all default values into our config variables before streaming
        # updated data into them.
        self.reset_config_variables()

        # Send ourselves all of our config variable assignments
        config_rpcs = self.config_database.stream_matching(8, self.name)
        for rpc in config_rpcs:
            if deferred:
                self._device.deferred_rpc(*rpc)
            else:
                self._device.rpc(*rpc)

        def _post_config_setup():
            config_assignments = self.latch_config_variables()
            self._logger.info("Latched config variables at reset for controller: %s", config_assignments)

            for system in self._post_config_subsystems:
                system.clear_to_reset(config_assignments)

        if deferred:
            self._device.deferred_task(_post_config_setup)
        else:
            _post_config_setup()

    def _handle_reset(self):
        """Reset this controller tile.

        This process will call _handle_reset() for all of the controller
        subsystem mixins in order to make sure they all return to their proper
        reset state.

        It will then reset all of the peripheral tiles to emulate the behavior
        of a physical POD where the controller tile cuts power to all
        peripheral tiles on reset for a clean boot.
        """

        super(ReferenceController, self)._handle_reset()

        self._clear_to_reset_condition(deferred=True)

        self._logger.info("Controller tile has finished resetting itself and will now reset each tile")
        self._device.reset_peripheral_tiles()

    def start(self, channel=None):
        """Start this conrtoller tile.

        This resets the controller to its reset state.

        Args:
            channel (IOTilePushChannel): the channel with a stream and trace
                routine for streaming and tracing data through a VirtualInterface
        """

        super(ReferenceController, self).start(channel)
        self._clear_to_reset_condition(deferred=False)

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

    @tile_rpc(*rpcs.RESET)
    def reset(self):
        """Reset the device."""

        self._device.reset_count += 1
        self._handle_reset()

        raise TileNotFoundError("Controller tile was reset via an RPC")

    @tile_rpc(0x1008, "", "L8xLL")
    def controller_info(self):
        """Get the controller UUID, app tag and os tag."""

        return [self._device.iotile_id, _pack_version(*self.os_info), _pack_version(*self.app_info)]


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
