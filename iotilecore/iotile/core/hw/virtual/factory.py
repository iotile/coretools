"""Dynamic factory for flexibly creating a virtual device."""

import json
import inspect
from typing import Optional, Union, Tuple
from iotile.core.dev import ComponentRegistry
from iotile.core.utilities import SharedLoop
from typedargs.exceptions import ArgumentError
from .virtualdevice_base import BaseVirtualDevice


def load_virtual_device(name: str, config: Optional[Union[str, dict]],
                        loop=SharedLoop) -> Tuple[BaseVirtualDevice, dict]:
    """Load a device either from a script or from an installed module"""

    if config is None:
        config_dict = {}  #type: dict
    elif isinstance(config, dict):
        config_dict = config
    else:
        if len(config) == 0:
            config_dict = {}
        elif config[0] == '#':
            # Allow passing base64 encoded json directly in the port string to ease testing.
            import base64
            config_str = str(base64.b64decode(config[1:]), 'utf-8')
            config_dict = json.loads(config_str)
        else:
            try:
                with open(config, "r") as conf:
                    data = json.load(conf)
            except IOError as exc:
                raise ArgumentError("Could not open config file", error=str(exc), path=config)

            if 'device' not in data:
                raise ArgumentError("Invalid configuration file passed to VirtualDeviceAdapter",
                                    device_name=name, config_path=config, missing_key='device')

            config_dict = data['device']

    reg = ComponentRegistry()

    if name.endswith('.py'):
        _name, device_factory = reg.load_extension(name, class_filter=BaseVirtualDevice, unique=True)
        return _instantiate_virtual_device(device_factory, config_dict, loop), config_dict

    seen_names = []
    for device_name, device_factory in reg.load_extensions('iotile.virtual_device',
                                                           class_filter=BaseVirtualDevice,
                                                           product_name="virtual_device"):
        if device_name == name:
            return _instantiate_virtual_device(device_factory, config_dict, loop), config_dict

        seen_names.append(device_name)

    raise ArgumentError("Could not find virtual_device by name", name=name, known_names=seen_names)


def _instantiate_virtual_device(factory, config, loop):
    """Safely instantiate a virtual device passing a BackgroundEventLoop if necessary."""

    kwargs = dict()

    sig = inspect.signature(factory)
    if 'loop' in sig.parameters:
        kwargs['loop'] = loop

    return factory(config, **kwargs)
