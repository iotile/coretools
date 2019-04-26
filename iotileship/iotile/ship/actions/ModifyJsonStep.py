import json
import copy

from iotile.ship.exceptions import RecipeActionMissingParameter

def modify_dict(data, key, value, create_if_missing=False):
    """
    Change (or add) a json key/value pair.

    Args:
        data (dict): The original data. This will not be modified.
        key (str|list): Either a string or a list of keys and subkeys specifing the key to change
        value (str): The value to change for the above key
        create_if_missing (bool): Set to true to create key if the last key in the list is not found
                Otherwise the function will throw a KeyError
    Returns:
        (dict): the final modified dict
    """
    data_copy = copy.deepcopy(data)
    key_copy = copy.deepcopy(key)

    delver = data_copy
    current_key = key_copy
    last_key = "Root"

    #Dig through the json, setting delver to the dict that contains the last key in "key"
    if isinstance(current_key, list):
        while len(current_key) > 1:
            if current_key[0] not in delver:
                raise KeyError("ModifyJsonStep Key Couldn't find Subkey {} in {}.".format(current_key[0], last_key))

            if len(current_key) > 2 and not isinstance(delver[current_key[0]], dict):
                raise KeyError("ModifyJsonStep The Value of {} is a {}, not a dict".format(current_key[0], type(delver[current_key])))

            last_key = current_key[0]
            delver = delver[current_key[0]]
            current_key.pop(0)

        final_key = current_key[0]
    elif isinstance(current_key, str):
        final_key = current_key

    if final_key not in delver and not create_if_missing:
        raise KeyError("ModifyJsonStep Key Couldn't find Subkey {} in {}.".format(final_key, last_key))

    delver[final_key] = value

    return data_copy


class ModifyJsonStep: #pylint: disable=too-few-public-methods
    """
    A Recipe Step used to change (or add) a json key/value pair.

    Args:
        key (str|list): Either a string or a list of keys and subkeys specifing the key to change
        value (str): The value to change for the above key
        path (str): The file path, relative to the Filesystem Manager's root, to the file to change
        create_if_missing (bool): Set to true to create key if the last key in the list is not found
                Otherwise the function will throw a KeyError
    """

    REQUIRED_RESOURCES = [('filesystem', 'filesystem_manager')]

    def __init__(self, args):
        if args.get('key') is None:
            raise RecipeActionMissingParameter("ModifyJsonStep Parameter Missing", parameter_name='key')
        if args.get('value') is None:
            raise RecipeActionMissingParameter("ModifyJsonStep Parameter Missing", parameter_name='value')
        if args.get('path') is None:
            raise RecipeActionMissingParameter("ModifyJsonStep Parameter Missing", parameter_name='path')

        self._key = args.get('key')
        self._value = str(args.get('value'))
        self._path = str(args.get('path'))
        self._create = bool(args.get('create_if_missing', False))


    def run(self, resources): #pylint: disable=missing-docstring
        root = resources['filesystem'].root
        fullpath = root.joinpath(self._path)

        with open(fullpath, "r") as infile:
            data = json.load(infile)

        result = modify_dict(data, self._key, self._value, self._create)

        with open(fullpath, "w") as outfile:
            json.dump(result, outfile, indent=2)
