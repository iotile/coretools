# This file is adapted from python code released by WellDone International
# under the terms of the LGPLv3.  WellDone International's contact information is
# info@welldone.org
# http://welldone.org
#
# Modifications to this file from the original created at WellDone International
# are copyright Arch Systems Inc.

from __future__ import print_function
from future.utils import viewitems
import os.path

def build_summary_cmd(target, source, env):
    """
    Build a text file with the status results for all of the unit tests in sources.
    sources should point to an array of strings corresponding to .status files.
    """

    some_failed = False

    targets = {}

    for node in source:
        path = str(node)

        name, targ, ext = parse_name(path)
        if ext != '.status':
            print("Ignoring non-status file %s, this file should not be in this list" % path)

        if targ not in targets:
            targets[targ] = []

        targets[targ].append((name, path))

    with open(str(target[0]), 'w') as f:
        f.write('Test Summary\n')

        for targ, tests in viewitems(targets):
            num_tests = len(tests)
            results = [test_passed(x[1]) for x in tests]
            tagged_tests = list(zip(tests, results))

            failed = [x for x in tagged_tests if x[1] is False]
            passed = [x for x in tagged_tests if x[1] is True]

            num_passed = len(passed)

            if num_passed != num_tests:
                some_failed = True

            f.write("\n## Target %s ##\n" % targ)
            f.write("%d/%d tests passed (%d%% pass rate)\n" % (num_passed, num_tests, (num_passed*100/num_tests)))

            for fail in failed:
                f.write("Test %s FAILED\n" % fail[0][0])

    with open(str(target[0]), "r") as f:
        for line in f.readlines():
            print(line.rstrip())

    #Raise a build error if some tests failed
    if some_failed:
        return 1

def test_passed(path):
    with open(path, 'r') as f:
        contents = f.read()
        result = contents.lstrip().rstrip()

        if result == 'PASSED':
            return True
        elif result == 'FAILED':
            return False
        else:
            raise ValueError('Invalid value in test status file %s, contents were %s' %(path, result))

def parse_name(path):
    base = os.path.basename(path)
    (name, ext) = os.path.splitext(base)

    (name, target) = name.split('@', 1)

    return (name, target, ext)
