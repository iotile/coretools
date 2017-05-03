"""Canonical list of config variables defined by iotile-core."""


def get_variables():
    """Get a dictionary of configuration variables."""

    prefix = "core"

    conf_vars = []
    conf_vars.append(["default-port", "string", "The default port to use for HardwareManager sessions if none is given"])

    return prefix, conf_vars
