import unit_test
import os
import arm
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

    def _find_test_functions(self, infile, arch):
        """Parse the unit test file and search for functions that start with test_."""

        parsed = ParsedCFile(infile, arch)
        test_functions = parsed.defined_functions(criterion=lambda x: x.startswith('test_'))
        print(test_functions)

    def build_target(self, target, summary_env):
        temp = template.RecursiveTemplate(QEMUSemihostedUnitTest.UnitTemplate, resource_filename(Requirement.parse("iotile-build"), "iotile/build/config/templates"), only_ext=".tpl")


        self._find_test_functions(self.files[0], target)
        test_dir = self.build_dirs(target)['objects']
        temp.render(test_dir)



        self._create_objects(target)

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

        ##Specify the output map file
        prog_env['LINKFLAGS'].extend(['-Xlinker', '-Map="%s"' % os.path.join(build_dirs['objects'], map_name)])
        prog_env.Clean(os.path.join(build_dirs['objects'], output_name), [os.path.join(build_dirs['objects'], map_name)])

        outfile = prog_env.Program(os.path.join(build_dirs['objects'], prog_env['OUTPUT']), prog_env.Glob(os.path.join(build_dirs['objects'], '*.c')))


unit_test.known_types['qemu_semihost_unit'] = QEMUSemihostedUnitTest
