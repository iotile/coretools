"""Mixin class to add property change tracking to an emulated device."""

from __future__ import unicode_literals, absolute_import, print_function
import json
from iotile.core.exceptions import ArgumentError


class EmulationMixin(object):
    """Mixin class to add property change tracking and state loading to a class.

    This mixin installs a __setattr__ overload that will track whenever
    a write happens to a property contained in _tracked_properties,
    recording the property name and its value.

    It also adds the ability to save and load the state of the emulated
    object so that you can come back to exactly where you were in the
    future and it adds the concept of scenarios, which are preloaded
    states that can be slightly customized.

    Args:
        address (int): The tile address if we have one, otherwise None
            for device wide changes that do not pertain to a specific
            tile.
        log (EmulationStateLog): The log where we should record our
            changes.
        properties (list of str): Optional list of property names that
            we should track.  If not specified, you can update later
            by adding property named to the `_tracked_properties` set.
    """

    def __init__(self, address, log, properties=None):
        self._emulation_log = log
        self._emulation_address = address

        if properties is None:
            properties = []

        self._tracked_properties = set(properties)
        self._known_scenarios = {}

    def __setattr__(self, name, value):
        if hasattr(self, '_tracked_properties') and name in self._tracked_properties:
            self._emulation_log.track_change(self._emulation_address, name, value)

        super(EmulationMixin, self).__setattr__(name, value)

    def _track_change(self, name, value):
        """Track that a change happened.

        This function is only needed for manually recording changes
        that are not captured by changes to properties of this object
        that are tracked automatically.
        """

        self._emulation_log.track_change(self._emulation_address, name, value)

    def dump_state(self):
        """Dump the current state of this emulated object as a dictionary.

        Returns:
            dict: The current state of the object that could be passed to load_state.
        """

        raise NotImplementedError("All subclasses must override dump_state")

    def restore_state(self, state):
        """Restore the current state of this emulated object.

        Args:
            state (dict): A previously dumped state produced by dump_state.
        """

        raise NotImplementedError("All subclasses must override restore_state")

    def save_state(self, out_path):
        """Save the current state of this emulated object to a file.

        Args:
            out_path (str): The path to save the dumped state of this emulated
                object.
        """

        state = self.dump_state()

        with open(out_path, "w") as outfile:
            json.dump(outfile, state, indent=4)

    def load_state(self, in_path):
        """Load the current state of this emulated object from a file.

        The file should have been produced by a previous call to save_state.

        Args:
            in_path (str): The path to the saved state dump that you wish
                to load.
        """

        with open(in_path, "w") as infile:
            state = json.load(infile)

        self.restore_state(state)

    def load_scenario(self, scenario_name, **kwargs):
        """Load a scenario into the emulated object.

        Scenarios are specific states of an an object that can be customized
        with keyword parameters.  Typical examples are:

          - data logger with full storage
          - device with low battery indication on

        Args:
            scenario_name (str): The name of the scenario that we wish to
                load.
            **kwargs: Any arguments that should be passed to configure
                the scenario.  These arguments will be passed directly
                to the scenario handler.
        """

        scenario = self._known_scenarios.get(scenario_name)
        if scenario is None:
            raise ArgumentError("Unknown scenario %s" % scenario_name, known_scenarios=list(self._known_scenarios))

        scenario(**kwargs)
