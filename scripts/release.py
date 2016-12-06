"""Release script to automatically release a component onto pypi

Usage: python release.py <component_name>-<expected version>

Component name should be one of:
    iotilecore
    iotilebuild
    iotilegateway
    iotile_transport_bled112

The version must match the version encoded in version.py in the respective
subdirectory for the component for the release to proceed.
"""

import sys
import os
import requests
import setuptools.sandbox
import subprocess
from twine.commands.upload import upload
import glob

comp_names = {
    'iotilecore': ['iotile-core', 'iotilecore'],
    'iotilebuild': ['iotile-build', 'iotilebuild'],
    'iotilegateway': ['iotile-gateway', 'iotilegateway'],
    'iotile_transport_bled112': ['iotile-transport-bled112', 'transport_plugins/bled112'] 
}

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

    global comp_names

    if len(sys.argv) < 2:
        raise EnvironmentError("Usage: python release.py <component_name>-<version>")

    comp = sys.argv[-1]
    name, vers = comp.split("-")

    if name not in comp_names:
        raise EnvironmentError("Invalid unknown release component name", name=name, known_names=comp_names.keys())

    return name, vers

def check_version(component, expected_version):
    """Make sure the package version in setuptools matches what we expect it to be
    """

    _, relative_compath = comp_names[component]

    compath = os.path.realpath(os.path.abspath(relative_compath))
    sys.path.insert(0, compath)

    import version

    if version.version != expected_version:
        raise EnvironmentError("Version mismatch during release, expected={}, found={}".format(expected_version, version.version))

def build_component(component):
    """Create an sdist and a wheel for the desired component
    """

    _, relative_compath = comp_names[component]

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
    
    print(os.environ.keys())
    if 'PYPI_USER' in os.environ and 'PYPI_PASS' in os.environ:
        pypi_user = os.environ['PYPI_USER']
        pypi_pass = os.environ['PYPI_PASS']
    else:
        pypi_user = None
        pypi_pass = None
        print("No PYPI user information in environment")

    print('"' + pypi_user + '"')
    print('"' + pypi_pass + '"')

    _, relative_compath = comp_names[component]
    distpath = os.path.join(relative_compath, 'dist', '*')
    distpath = os.path.realpath(os.path.abspath(distpath))
    dists = glob.glob(distpath)

    if pypi_user is None:
        args = ['twine', 'upload', distpath]
    else:
        args = ['twine', 'upload', '-u', pypi_user, '-p', pypi_pass, distpath]

    #Invoke upload this way since subprocess call of twine cli has cross platform issues
    upload(dists, 'pypi', False, None, pypi_user, pypi_pass, None, None, '~/.pypirc', False, None, None, None)

def main():
    component, version = get_release_component()
    check_version(component, version)
    build_component(component)
    upload_component(component)
    send_slack_message('Released {} version {} to PYPI'.format(component, version))

if __name__ == '__main__':
    main()
