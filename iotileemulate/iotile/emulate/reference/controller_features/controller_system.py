"""Base class for controller subsystems."""

import asyncio
from iotile.core.exceptions import InternalError

class ControllerSubsystemBase:
    """Base class for Controller subsystems.

    This class allows subsystems to define tasks that run in the background
    and are automatically associated with the parent controller.  It also
    allows the subsytems to update an `initialized` Event that lets the
    controller know when their background tasks are up and running.

    Args:
        emulator (EmulationLoop): The underlying emulation loop that all
            tasks should be added to.
    """

    def __init__(self, emulator):
        self._emulator = emulator
        self.initialized = emulator.create_event()

    async def _reset_vector(self):
        """Initialize any background tasks associated with this subsystem.

        Subclasses that choose to override this method must set the
        self.initialized Event() inside their reset vector once it starts up.
        """

        self.initialized.set()

    def clear_to_reset(self, config_vars):
        """Clear all volatile information across a reset.

        Classes that override this method must call super().clear_to_reset()
        to ensure that their base class is initialized correctly.

        Args:
            config_vars (dict): The map of all config variables that are
                declared on the controller.
        """

        self.initialized.clear()

    async def initialize(self, timeout=2.0):
        """Launch any background tasks associated with this subsystem.

        This method will synchronously await self.initialized() which makes
        sure that the background tasks start up correctly.
        """

        if self.initialized.is_set():
            raise InternalError("initialize called when already initialized")

        self._emulator.add_task(8, self._reset_vector())

        await asyncio.wait_for(self.initialized.wait(), timeout=timeout)
