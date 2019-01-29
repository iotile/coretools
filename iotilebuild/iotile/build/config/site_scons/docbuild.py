from iotile.build.utilities import render_template, resource_path


def generate_doxygen_file(output_path, iotile):
    """Fill in our default doxygen template file with info from an IOTile

    This populates things like name, version, etc.

    Arguments:
        output_path (str):  a string path for where the filled template should go
        iotile (IOTile): An IOTile object that can be queried for information
    """

    mapping = {}

    mapping['short_name'] = iotile.short_name
    mapping['full_name'] = iotile.full_name
    mapping['authors'] = iotile.authors
    mapping['version'] = iotile.version

    render_template('doxygen.txt.tpl', mapping, out_path=output_path)


def doxygen_source_path():
    """Return the absolute path to the doxygen template for dependency linking."""

    return resource_path('templates/doxygen.txt.tpl')
