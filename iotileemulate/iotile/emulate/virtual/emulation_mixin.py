"""Mixin class to add property change tracking to an emulated device."""

import json
from enum import IntEnum
from iotile.core.exceptions import ArgumentError


class EmulationMixin(object):
    """Mixin class to add property change tracking and state loading to a class.

    This mixin installs a __setattr__ overload that will track whenever a
    write happens to a property contained in _tracked_properties, recording
    the property name and its value.

    It also adds the ability to save and load the state of the emulated object
    so that you can come back to exactly where you were in the future and it
    adds the concept of scenarios, which are preloaded states that can be
    slightly customized with keyword arguments.

    This base class provides standard emulation behavior to both
    EmulatedDevice and EmulatedTile.

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

    def _track_change(self, name, value, formatter=None):
        """Track that a change happened.

        This function is only needed for manually recording changes that are
        not captured by changes to properties of this object that are tracked
        automatically.  Classes that inherit from `emulation_mixin` should
        use this function to record interesting changes in their internal
        state or events that happen.

        The `value` parameter that you pass here should be a native python
        object best representing what the value of the property that changed
        is.  When saved to disk, it will be converted to a string using:
        `str(value)`.  If you do not like the string that would result from
        such a call, you can pass a custom formatter that will be called as
        `formatter(value)` and must return a string.

        Args:
            name (str): The name of the property that changed.
            value (object): The new value of the property.
            formatter (callable): Optional function to convert value to a
                string.  This function will only be called if track_changes()
                is enabled and `name` is on the whitelist for properties that
                should be tracked.  If `formatter` is not passed or is None,
                it will default to `str`
        """

        self._emulation_log.track_change(self._emulation_address, name, value, formatter)

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

        # Remove all IntEnums from state since they cannot be json-serialized on python 2.7
        # See https://bitbucket.org/stoneleaf/enum34/issues/17/difference-between-enum34-and-enum-json
        state = _clean_intenum(state)

        with open(out_path, "w") as outfile:
            json.dump(state, outfile, indent=4)

    def load_state(self, in_path):
        """Load the current state of this emulated object from a file.

        The file should have been produced by a previous call to save_state.

        Args:
            in_path (str): The path to the saved state dump that you wish
                to load.
        """

        with open(in_path, "r") as infile:
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

    def register_scenario(self, scenario_name, handler):
        """Register a scenario handler for this object.

        Scenario handlers are callable functions with no positional arguments
        that can be called by name with the load_scenario function and should
        prepare the emulated object into a known state.  The purpose of a
        scenario is to make it easy to get a device into a specific state for
        testing purposes that may otherwise be difficult or time consuming to
        prepare on the physical, non-emulated device.

        Args:
            scenario_name (str): The name of this scenario that can be passed to
                load_scenario later in order to invoke the scenario.
            handler (callable): A callable function that takes no positional
                arguments and can prepare this object into the given scenario
                state.  It may take required or optional keyword arguments that
                may be passed to `load_scenario` if needed.
        """

        if scenario_name in self._known_scenarios:
            raise ArgumentError("Attempted to add the same scenario name twice", scenario_name=scenario_name,
                                previous_handler=self._known_scenarios[scenario_name])

        self._known_scenarios[scenario_name] = handler


def _clean_intenum(obj):
    """Remove all IntEnum classes from a map."""

    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, IntEnum):
                obj[key] = value.value
            elif isinstance(value, (dict, list)):
                obj[key] = _clean_intenum(value)
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            if isinstance(value, IntEnum):
                obj[i] = value.value
            elif isinstance(value, (dict, list)):
                obj[i] = _clean_intenum(value)

    return obj
