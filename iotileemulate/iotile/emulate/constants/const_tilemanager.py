"""Constants related to the TileManager subsystem on an IOTile controller."""

from enum import IntEnum

class RunLevel(IntEnum):
    """Possible directives returned to a tile upon registration.

    These run level directives tell the tile if and when it should pass
    control to application firmware.  A tile's run level is assigned exactly
    once when it resets itself and calls the REGISTER_TILE rpc.

    The run level is then fixed until the tile is reset at which point a new
    run level can be received from the TileBus controller.
    """

    START_IMMEDIATELY = 0
    """Pass control to application firmware immediately.

    This run level is not used inside physical IOTile devices because it does
    not provide the controller with time to safely stream configuration
    information to the POD before the application firmware runs and could
    potentially reference the config variables.

    The START_IMMEDIATELY run level exists to allow for unit testing scenarios
    when tiles should run independently of a controller.
    """

    START_ON_COMMAND = 1
    """Wait until a RUN_APPLICATION rpc is received before passing control to app.

    This is the standard run level returned to a physical tile.  It tells the
    tile's executive to wait until the controller sends it a RUN_APPLICATION
    rpc, at which point it can pass control to the any loaded application
    firmware.
    """

    SAFE_MODE = 2
    """The tile should enter safe mode, which means no application control.

    Safe mode tells the tile executive that the application firmware is
    potentially misbehaving and should not be run.  This prevents
    loss-of-control situations where a misbehaving tile takes control of
    TileBus and prevents the receipt of any messages telling it to stop
    talking.

    Since the controller can cut power to all tiles and the tile executive
    waits before running application firmware, there is always a de-bricking
    mechanism by cutting power to the tile and then telling it to enter safe
    mode, whereby executive RPC functions can be executed including
    bootloading.
    """

    DORMANT = 3
    """The tile should enter a deep sleep state until reset by the controller.

    This state is not currently used but is designed to allow infrequently
    used tiles to be put into an ultra-low-power state that does not preserve
    RAM contents or allow for processing of RPCs.
    """

    BOOTLOAD = 4
    """The tile should immediately bootload firmware from the controller.

    This starts a tile's firmware upgrade process where it passes control to
    its bootloader that begins pulling firmware from the controller and
    updating itself.
    """


class TileState(IntEnum):
    """Possible states that a tile can have inside the TileManager cache.

    These states represent the phase of the tile lifecycle that the tile
    is currently known to be in.
    """

    INVALID = 0
    """This slot in the tile manager cache does not represent a tile."""

    JUST_REGISTERED = 1
    """The tile has just sent the REGISTER_TILE rpc.

    This state changes to BEING_CONFIGURED when the controller starts sending
    config variables to the tile.
    """

    BEING_CONFIGURED = 2
    """The tile is currently receiving config variables from the controller."""

    RUNNING = 3
    """The tile has received the START_APPLICATION rpc from the controller."""

    SAFE_MODE = 4
    """The controller replied to the tile's REGISTER_TILE rpc with RunLevel.SAFE_MODE."""

    DORMANT = 5
    """The controller replied to the tile's REGISTER_TILE rpc with RunLevel.DORMANT."""

    SHOULD_BOOTLOAD = 6
    """The controller replied to the tile's REGISTER_TILE rpc with RunLevel.BOOTLOAD."""

    BOOTLOADING = 7
    """The tile was told to bootload and it subsequently reported that it had started."""

    FINISHED_BOOTLOADING = 8
    """The tile was told to bootload and it subsequently reported that it had finished."""

    UNRECOVERABLE_ERROR = 9
    """The tile has performed an action that indicates it had a fatal error."""
