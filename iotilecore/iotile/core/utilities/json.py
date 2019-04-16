''' Common functions for working with json files, including write/rename rewriting
'''

import json
import os
import platform



def load_config(path):
    ''' Read json from file, return python dictionary

    Args:
        path (str): Path to json file to read
    '''

    with open(path, "r") as infile:
        return json.load(infile)


def persist_config(config, path):
    ''' Write dictionary back to json file
    If run on a non-Windows system, perform an atomic rewrite of the file

    Args:
        config (dict): Dictionary to write out
        path (str): Path to json file to write to
    '''

    if platform.system() == 'Windows':
        with open(path, "w") as outfile:
            json.dump(config, outfile, indent=4)
    else:
        new_path = path + '.new'

        with open(new_path, "w") as outfile:
            json.dump(config, outfile, indent=4)

        os.rename(os.path.realpath(new_path), os.path.realpath(path))
