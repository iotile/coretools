import shutil
import subprocess
import unit_test
import os
from future.utils import viewitems
import arm
from SCons.Environment import Environment
from SCons.Script import Copy, Builder
from iotile.core.exceptions import BuildError
from iotile.build.utilities import render_recursive_template, render_template_inplace
from cfileparser import ParsedCFile


class QEMUSemihostedUnitTest(unit_test.UnitTest):
    """A unit test run in gnuarmeclipse qemu.

    The unit test is compiled using a template containing the unity
    testing framework and run in a semihosted fashion in qemu targeting
    a generic Cortex M processor.
    """

    UNIT_TEMPLATE = "qemu_semihost_unit"

    def _parse_module(self, mod):
        _inc_dirs, sources, _headers = unit_test.find_sources('firmware/src')

        if mod.endswith('.c'):
            mod = mod[:-2]

        if mod not in sources:
            raise BuildError("Could not find module specified: %s" % mod)

        self.files.append(sources[mod])

    def _find_test_functions(self, infile, arch):
        """Parse the unit test file and search for functions that start with `test_`."""

        parsed = ParsedCFile(infile, arch)
        test_functions = parsed.defined_functions(criterion=lambda x: x.startswith('test_'))
        return test_functions

    def build_target(self, target, summary_env):
        """Build this unit test for the given target."""

        test_dir = self.build_dirs(target)['objects']

        _c_files, _all_files = self._copy_files(test_dir)

        # Compile all .c files to .o files
        test_elf = self._create_objects(target)

        # Now create a task to run the test
        logpath = self.get_path('rawlog', target)
        statuspath = self.get_path('status', target)

        self._run_test(logpath, statuspath, test_elf)
        summary_env['TESTS'].append(statuspath)

    def _copy_files(self, target_dir):
        """Copy test harness and file-under-test."""

        builder = Builder(action=recursive_template_action,
                          emitter=recursive_template_emitter)

        _inc_dirs, _sources, headers = unit_test.find_sources('firmware/src')

        # Render the template
        env = Environment(tools=[], BUILDERS={'render': builder})
        env['RECURSIVE_TEMPLATE'] = self.UNIT_TEMPLATE
        template_files = env.render([os.path.join(target_dir, '.timestamp')], [])

        test_files = []
        for infile in self.files:
            test_file = env.Command([os.path.join(target_dir, os.path.basename(infile))], [infile], action=Copy("$TARGET", "$SOURCE"))
            test_files.append(test_file)

        # Copy all headers into the unit test
        for _basename, infile in viewitems(headers):
            test_file = env.Command([os.path.join(target_dir, os.path.basename(infile))], [infile], action=Copy("$TARGET", "$SOURCE"))
            test_files.append(test_file)

        all_files = template_files + test_files
        c_files = [str(x) for x in all_files if str(x).endswith('.c')]

        return c_files, all_files

    def _create_objects(self, target):
        elfname = 'qemu_unit_test'

        output_name = '%s_%s.elf' % (elfname, target.arch_name(),)
        map_name = '%s_%s.map' % (elfname, target.arch_name(),)

        build_dirs = self.build_dirs(target)

        # Retarget for unit tests, since qemu only supports the cortex-m0
        target = target.retarget()
        target.settings['cpu'] = 'cortex-m0plus'
        target.settings['cflags'] = ["-mthumb", "-Wall", "-pedantic", "-Wextra", "-Wshadow", "-Os", "-g", "-fno-builtin", "-ffunction-sections", "-fdata-sections"]
        target.settings['asflags'] = ["-Wall"]
        target.settings['ldflags'] = ["-mthumb", "-Xlinker", "--gc-sections", "--specs=nano.specs", "-lc", "-lnosys", "-nostartfiles"]       
        prog_env = arm.setup_environment(target)

        # Convert main.c.tpl into main.c
        _main_c = prog_env.Command([os.path.join(build_dirs['objects'], 'main.c')], [os.path.join(build_dirs['objects'], os.path.basename(self.files[0])), os.path.join(build_dirs['objects'], 'main.c.tpl')], action=generate_main_c)

        prog_env['OUTPUT'] = output_name
        prog_env['BUILD_DIR'] = build_dirs['objects']
        prog_env['OUTPUT_PATH'] = os.path.join(build_dirs['test'], output_name)
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
    except subprocess.CalledProcessError as exc:
        passed = False
        logcontents = exc.output
    except Exception as exc:
        passed = False
        logcontents = "Error running command: %s" % str(exc)

    # Write the log file

    if type(logcontents) is str:
        logcontents = logcontents.encode()

    with open(str(target[0]), "wb") as logfile:
        logfile.write(logcontents)

    # Write the status file
    with open(str(target[1]), "w") as statusfile:
        if passed:
            statusfile.write('PASSED')
        else:
            statusfile.write('FAILED')


def generate_main_c(target, source, env):
    """Parse the unit test file and search for functions that start with `test_`."""

    parsed = ParsedCFile(str(source[0]), env['ARCH'])
    test_functions = parsed.defined_functions(criterion=lambda x: x.startswith('test_'))

    render_template_inplace(str(source[1]), {'tests': test_functions})


def recursive_template_emitter(target, source, env):
    """Emit all of the files generated by a recursive template."""

    outdir = os.path.dirname(str(target[0]))

    files, _dirs = render_recursive_template(env['RECURSIVE_TEMPLATE'], {}, outdir, preserve=["main.c.tpl"], dry_run=True)
    target.extend([os.path.join(outdir, x) for x in files])

    for outfile in files:
        source.append(files[outfile][1])

    return target, source


def recursive_template_action(target, source, env):
    """Render a recursive template."""

    outdir = os.path.dirname(str(target[0]))
    render_recursive_template(env['RECURSIVE_TEMPLATE'], {}, outdir, preserve=["main.c.tpl"])
