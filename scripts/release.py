"""Release script to automatically release a component onto pypi

Usage: python release.py <component_name>-<expected version>

Component name should be one of the components defined in components.py

The version must match the version encoded in version.py in the respective
subdirectory for the component for the release to proceed.
"""

from __future__ import unicode_literals, print_function, absolute_import
import argparse
import sys
import os
import glob
import requests
import setuptools.sandbox
from twine.commands.upload import upload
from components import comp_names

def build_parser():
    """Build argument parsers."""

    parser = argparse.ArgumentParser("Release packages to pypi")
    parser.add_argument('--check', '-c', action="store_true", help="Do a dry run without uploading")
    parser.add_argument('component', help="The component to release as component-version")
    return parser

def send_slack_message(message):
    """Send a message to the slack channel #coretools
    """

    if 'SLACK_WEB_HOOK' not in os.environ:
        raise EnvironmentError("Could not find SLACK_WEB_HOOK environment variable")

    webhook = os.environ['SLACK_WEB_HOOK']

    r = requests.post(webhook, json={'text':message, 'username': 'Release Bot'})
    if r.status_code != 200:
        raise RuntimeError("Could not post message to slack channel")

def get_release_component(comp):
    """Split the argument passed on the command line into a component name and expected version
    """

    name, vers = comp.split("-")

    if name not in comp_names:
        print("Known components:")
        for comp in comp_names:
            print("- %s" % comp)

        raise EnvironmentError("Unknown release component name '%s'" % name)

    return name, vers


def check_compatibility(name):
    """Verify if we can release this component on the running interpreter.

    All components are released from python 2.7 by default unless they specify
    that they are python 3 only, in which case they are released from python 3.6
    """

    comp = comp_names[name]

    if sys.version_info.major < 3 and comp.compat == "python3":
        return False

    if sys.version_info.major >= 3 and comp.compat != "python3":
        return False

    return True


def check_version(component, expected_version):
    """Make sure the package version in setuptools matches what we expect it to be
    """

    comp = comp_names[component]

    compath = os.path.realpath(os.path.abspath(comp.path))
    sys.path.insert(0, compath)

    import version

    if version.version != expected_version:
        raise EnvironmentError("Version mismatch during release, expected={}, found={}".format(expected_version, version.version))


def build_component(component):
    """Create an sdist and a wheel for the desired component
    """

    comp = comp_names[component]

    curr = os.getcwd()
    os.chdir(comp.path)

    args = ['-q', 'clean', 'sdist', 'bdist_wheel']
    if comp.compat == 'universal':
        args.append('--universal')

    try:
        setuptools.sandbox.run_setup('setup.py', args)
    finally:
        os.chdir(curr)

def upload_component(component):
    """Upload a given component to pypi

    The pypi username and password must either be specified in a ~/.pypirc
    file or in environment variables PYPI_USER and PYPI_PASS
    """

    if 'PYPI_USER' in os.environ and 'PYPI_PASS' in os.environ:
        pypi_user = os.environ['PYPI_USER']
        pypi_pass = os.environ['PYPI_PASS']
    else:
        pypi_user = None
        pypi_pass = None
        print("No PYPI user information in environment")

    comp = comp_names[component]
    distpath = os.path.join(comp.path, 'dist', '*')
    distpath = os.path.realpath(os.path.abspath(distpath))
    dists = glob.glob(distpath)

    if pypi_user is None:
        args = ['twine', 'upload', distpath]
    else:
        args = ['twine', 'upload', '-u', pypi_user, '-p', pypi_pass, distpath]

    #Invoke upload this way since subprocess call of twine cli has cross platform issues
    upload(dists, 'pypi', False, None, pypi_user, pypi_pass, None, None, '~/.pypirc', False, None, None, None)


def get_release_notes(component, version):
    comp = comp_names[component]
    notes_path = os.path.join(comp.path, 'RELEASE.md')

    try:
        with open(notes_path, "r") as f:
            lines = f.readlines()
    except IOError:
        print("ERROR: Could not find release notes file RELEASE.md")
        sys.exit(1)

    release_lines = {y[2:].strip(): x for x, y in enumerate(lines) if y.startswith('##')}

    if version not in release_lines:
        print("ERROR: Could not find release notes for current release version")
        sys.exit(1)

    start_line = release_lines[version]
    past_releases = [x for x in release_lines.values() if x > start_line]

    if len(past_releases) == 0:
        release_string = "".join(lines[start_line+1:])
    else:
        release_string = "".join(lines[start_line:min(past_releases)])

    if len(release_string) == 0:
        print("ERROR: Empty release notes for current release version")
        sys.exit(1)

    return release_string

def main():
    parser = build_parser()
    args = parser.parse_args()

    component, version = get_release_component(args.component)
    check_version(component, version)
    compat = check_compatibility(component)

    # We do not return an error so this script can be called on both python 2
    # and python 3 and just release once without failing on the other
    # interpreter.
    if not compat:
        print("Not releasing {} because of interpreter version mismatch.".format(component))
        print("Run this script from a different python version.")
        return

    build_component(component)

    release_notes = get_release_notes(component, version)

    if args.check:
        print("Check Release\nName: {}\nVersion: {}".format(component, version))
        print("Compatibility: {}".format(comp_names[component].compat))
        print("\nRelease Notes:\n" + release_notes)

    else:
        upload_component(component)
        send_slack_message('*Released {0} version {1} to PYPI*\n\nRelease Notes for version {1}:\n```\n{2}```'.format(component, version, release_notes))


if __name__ == '__main__':
    main()
