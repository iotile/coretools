"""Canonical list of config variables defined by iotile-build"""


def get_variables():
    prefix = "build"

    conf_vars = [["show-commands", "bool", "Show the actual commands used to compile code", "false"]]

    return prefix, conf_vars
