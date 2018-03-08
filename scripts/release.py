"""Release script to automatically release a component onto pypi

Usage: python release.py <component_name>-<expected version>

Component name should be one of the components defined in components.py

The version must match the version encoded in version.py in the respective
subdirectory for the component for the release to proceed.
"""

from __future__ import unicode_literals, print_function, absolute_import
import sys
import os
import glob
import requests
import setuptools.sandbox
from twine.commands.upload import upload
from components import comp_names

def send_slack_message(message):
    """Send a message to the slack channel #coretools
    """

    if 'SLACK_WEB_HOOK' not in os.environ:
        raise EnvironmentError("Could not find SLACK_WEB_HOOK environment variable")

    webhook = os.environ['SLACK_WEB_HOOK']

    r = requests.post(webhook, json={'text':message, 'username': 'Release Bot'})
    if r.status_code != 200:
        raise RuntimeError("Could not post message to slack channel")

def get_release_component():
    """Split the argument passed on the command line into a component name and expected version
    """

    if len(sys.argv) < 2:
        raise EnvironmentError("Usage: python release.py <component_name>-<version>")

    comp = sys.argv[-1]
    name, vers = comp.split("-")

    if name not in comp_names:
        print("Known components:")
        for comp in comp_names:
            print("- %s" % comp)

        raise EnvironmentError("Unknown release component name '%s'" % name)

    return name, vers

def check_version(component, expected_version):
    """Make sure the package version in setuptools matches what we expect it to be
    """

    _, relative_compath, _py3 = comp_names[component]

    compath = os.path.realpath(os.path.abspath(relative_compath))
    sys.path.insert(0, compath)

    import version

    if version.version != expected_version:
        raise EnvironmentError("Version mismatch during release, expected={}, found={}".format(expected_version, version.version))

def build_component(component):
    """Create an sdist and a wheel for the desired component
    """

    _, relative_compath, _py3 = comp_names[component]

    curr = os.getcwd()
    os.chdir(relative_compath)
    try:
        setuptools.sandbox.run_setup('setup.py', ['-q', 'clean', 'sdist', 'bdist_wheel'])
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

    _, relative_compath, _py3 = comp_names[component]
    distpath = os.path.join(relative_compath, 'dist', '*')
    distpath = os.path.realpath(os.path.abspath(distpath))
    dists = glob.glob(distpath)

    if pypi_user is None:
        args = ['twine', 'upload', distpath]
    else:
        args = ['twine', 'upload', '-u', pypi_user, '-p', pypi_pass, distpath]

    #Invoke upload this way since subprocess call of twine cli has cross platform issues
    upload(dists, 'pypi', False, None, pypi_user, pypi_pass, None, None, '~/.pypirc', False, None, None, None)

def get_release_notes(component, version):
    _, relative_compath, _py3 = comp_names[component]
    notes_path = os.path.join(relative_compath, 'RELEASE.md')

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
    past_releases = [x for x in release_lines.itervalues() if x > start_line]

    if len(past_releases) == 0:
        release_string = "".join(lines[start_line+1:])
    else:
        release_string = "".join(lines[start_line:min(past_releases)])

    if len(release_string) == 0:
        print("ERROR: Empty release notes for current release version")
        sys.exit(1)

    return release_string

def main():
    if len(sys.argv) < 2:
        print("Usage: release.py [--check] <component_name>-<version>")
        sys.exit(1)

    dry_run = False
    if sys.argv[-2] == '--check':
        dry_run = True

    component, version = get_release_component()
    check_version(component, version)
    build_component(component)

    release_notes = get_release_notes(component, version)

    if dry_run:
        print("Check Release\nName: {}\nVersion: {}".format(component, version))
        print("Release Notes:\n" + release_notes)
    else:
        upload_component(component)
        send_slack_message('*Released {} version {} to PYPI*\n\nRelease Notes for version {}:\n```\n{}```'.format(component, version, version, release_notes))

if __name__ == '__main__':
    main()
