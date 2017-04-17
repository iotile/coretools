import shutil
import subprocess
import unit_test
import os
import arm
from SCons.Environment import Environment
from pkg_resources import resource_filename, Requirement
import iotile.build.utilities.template as template
from cfileparser import ParsedCFile


class QEMUSemihostedUnitTest(unit_test.UnitTest):
    """A unit test run in gnuarmeclipse qemu.

    The unit test is compiled using a template containing the unity
    testing framework and run in a semihosted fashion in qemu targeting
    a generic Cortex M processor.
    """

    UnitTemplate = "qemu_semihost_unit"

    def __init__(self, files, ignore_extra_attributes=False):
        """Constructor.

        Args:
            files (list): A list of files to include in the unit test
        """

        super(QEMUSemihostedUnitTest, self).__init__(files, ignore_extra_attributes)

        self.template = template.RecursiveTemplate(QEMUSemihostedUnitTest.UnitTemplate, resource_filename(Requirement.parse("iotile-build"), "iotile/build/config/templates"), remove_ext=True, only_ext=".tpl")

        # Make a note that we are adding all of our template files as intermediates
        for outfile in self.template.iter_output_files():
            self.add_intermediate(outfile, 'objects')

        for outfile in files:
            filename = os.path.basename(outfile)
            self.add_intermediate(filename, 'objects')

    def _find_test_functions(self, infile, arch):
        """Parse the unit test file and search for functions that start with `test_`."""

        parsed = ParsedCFile(infile, arch)
        test_functions = parsed.defined_functions(criterion=lambda x: x.startswith('test_'))
        return test_functions

    def build_target(self, target, summary_env):
        """Build this unit test for the given target."""

        test_dir = self.build_dirs(target)['objects']

        # Copy over the test file itself
        for file in self.files:
            filename = os.path.basename(file)
            shutil.copyfile(file, os.path.join(test_dir, filename))

        # Now copy over all of the test files so that we can find unity.h
        self.template.add({'tests': []})
        self.template.render(test_dir)
        self.template.clear()

        # Now search for test functions
        test_file = os.path.join(test_dir, os.path.basename(self.files[0]))
        test_functions = self._find_test_functions(test_file, target)

        # Now recreate the test from the template with test files included
        self.template.add({'tests': test_functions})
        self.template.render(test_dir)
        self.template.clear()

        # Now create the ELF containing the unit test
        test_elf = self._create_objects(target)

        # Now create a task to run the test
        logpath = self.get_path('rawlog', target)
        statuspath = self.get_path('status', target)

        self._run_test(logpath, statuspath, test_elf)
        summary_env['TESTS'].append(statuspath)

    def _create_objects(self, target):
        elfname = 'qemu_unit_test'

        output_name = '%s_%s.elf' % (elfname, target.arch_name(),)
        map_name = '%s_%s.map' % (elfname, target.arch_name(),)

        build_dirs = self.build_dirs(target)

        prog_env = arm.setup_environment(target)

        prog_env['OUTPUT'] = output_name
        prog_env['BUILD_DIR'] = build_dirs['objects']
        prog_env['OUTPUT_PATH'] = os.path.join(build_dirs['objects'], output_name)
        prog_env['MODULE'] = elfname

        ldscript = os.path.join(build_dirs['objects'], 'qemu_semihost.ld')
        lddir = os.path.abspath(os.path.dirname(ldscript))
        prog_env['LIBPATH'] += [lddir]

        prog_env['LINKFLAGS'].append('-T"%s"' % ldscript)

        # Specify the output map file
        prog_env['LINKFLAGS'].extend(['-Xlinker', '-Map="%s"' % os.path.join(build_dirs['objects'], map_name)])

        # Build the ELF
        outfile = prog_env.Program(prog_env['OUTPUT_PATH'], prog_env.Glob(os.path.join(build_dirs['objects'], '*.c')))

        # Make a note that we should clean everything up when the ELF is no longer needed
        prog_env.Clean(outfile, [os.path.join(build_dirs['objects'], map_name)])
        prog_env.Clean(outfile, self.get_intermediates(target))

        return outfile

    def _run_test(self, logpath, statuspath, test_elf):
        """Run a test elf under qemu."""

        env = Environment()
        env.Command([logpath, statuspath], [test_elf], action=env.Action(run_qemu_command, "Running Test"))


unit_test.known_types['qemu_semihost_unit'] = QEMUSemihostedUnitTest


def run_qemu_command(target, source, env):
    """Run qemu on a unit test and capture the output."""

    test_args = ['qemu-system-gnuarmeclipse', '-board', 'STM32F0-Discovery', '-nographic', '-monitor', 'null', '-serial', 'null', '--semihosting-config', 'enable=on,target=native', '-d', 'unimp,guest_errors', '-image']
    test_args.append(str(source[0]))

    passed = True

    try:
        logcontents = subprocess.check_output(test_args, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError, exc:
        passed = False
        logcontents = exc.output
    except Exception, exc:
        passed = False
        logcontents = "Error running command: %s" % str(exc)

    # Write the log file
    with open(str(target[0]), "wb") as logfile:
        logfile.write(logcontents)

    # Write the status file
    with open(str(target[1]), "w") as statusfile:
        if passed:
            statusfile.write('PASSED')
        else:
            statusfile.write('FAILED')
