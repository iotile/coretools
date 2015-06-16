#pic12_unit.py
#Routines for building unit tests for the pic12 processor
from SCons.Script import *
from SCons.Environment import Environment
import os
import os.path
import utilities
import pic12

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from pymomo.gpysim import log
from pymomo.hex8 import symbols
from pymomo.exceptions import *

def build_unittest(test, arch, summary_env, cmds=None):
	"""
	Build a hex file from the source files test_files for the indicated chip
	If cmds is passed, replace the generic run command to gpsim with the commands
	listed in the passed file
	"""

	#Extract information from test
	#Allow files to be renamed with architecture extensions automatically
	test_files = filter(lambda x: x is not None, map(lambda x: test.find_support_file(x, arch), test.files))

	name = test.name
	type = test.type

	env = Environment(tools=['xc8_compiler', 'patch_mib12', 'merge_mib12_app', 'merge_mib12_sym', 'gpsim_runner'], ENV = os.environ)
	env['ORIGINAL_ARCH'] = arch
	env['TEST'] = test

	#Configure for app module or exec
	if type.startswith("executive"):
		orig_name = 'mib12_executive_symbols'
		env['ARCH'] = arch.retarget(remove=['exec'], add=['app'])
		pic12.configure_env_for_xc8(env, force_app=True)
		test_harness = ['../test/pic12/exec_harness/mib12_exec_unittest.c', '../test/pic12/exec_harness/mib12_api.as', '../test/pic12/gpsim_logging/test_log.as', '../test/pic12/gpsim_logging/test_mib.as']
	elif type == "application":
		orig_name = "mib12_app_module_symbols"

		env['ARCH'] = arch.retarget(remove=['app'], add=['exec'])

		pic12.configure_env_for_xc8(env, force_exec=True)
		test_harness = ['../test/pic12/app_harness/mib12_app_unittest.c', '../test/pic12/app_harness/mib12_test_api.as', '../test/pic12/gpsim_logging/test_log.as']
	else:
		raise BuildError("Invalid unit test type specified. Should start with executive or application.", type=type)

	orig_symfile = orig_name + '.h'
	orig_symtab = orig_name + '.stb'

	dirs = arch.build_dirs()

	builddir = dirs['build']
	testdir = os.path.join(dirs['test'], name, 'objects')
	finaldir = dirs['output']
	outdir = os.path.join(dirs['test'], name)
	
	env.AppendENVPath('PATH','../../tools/scripts')

	incs = []
	incs.append('.')
	incs.append('src')
	incs.append('src/mib')
	incs.append(testdir)
	incs.extend(arch.property('test_includes', []))

	env['INCLUDE'] += incs

	#Copy over the symbol file from the module we're testing so we can reference it
	symfile = Command(os.path.join(testdir, 'symbols.h'),  os.path.join(builddir, orig_symfile), Copy("$TARGET", "$SOURCE"))
	testee_symtab = Command(os.path.join(testdir, 'symbols.stb'),  os.path.join(builddir, orig_symtab), Copy("$TARGET", "$SOURCE"))

	symtab = env.merge_mib12_symbols([os.path.join(outdir, 'symbols.stb')], [testee_symtab, os.path.join(testdir, name + '_unit.sym')])

	#Load in all of the xc8 configuration from build_settings
	sim = arch.property('gpsim_proc')

	env['TESTCHIP'] = sim
	env['TESTNAME'] = name
	env['TESTAPPEND'] = arch.arch_name()
	env['EXTRACMDS'] = cmds

	#Must do this in 1 statement so we don't modify test_files
	srcfiles = test_files + test_harness

	#If we are compiling a special mib block, add it in
	if test.mibfile is not None:
		cmdmap = pic12.compile_mib(env, test.mibfile, testdir)
		srcfiles += cmdmap

	apphex = env.xc8(os.path.join(testdir, name + '_unit.hex'), srcfiles)
	env.Depends(apphex[0], symfile)

	if type.startswith("executive"):
		app_start = env['CHIP'].app_rom[0] + 2

		#Executive integration tests run the entire executive startup routine
		#Regular integration tests skip it to save time (1 second delay for registration)
		#and to avoid triggering any bugs in the executive code since these are unit tests.
		#for specific routines.
		if type == "executive_integration":
			#Patch in the application checksum that's appropriate here
			highhex = env.Command(os.path.join(testdir, name + '_unit_checksummed.hex'), apphex[0], action=env.Action(pic12.checksum_insertion_action, "Patching Application Checksum"))
			lowhex = os.path.join(builddir, 'mib12_executive_patched.hex')
		else:
			lowhex = env.Command(os.path.join(testdir, 'mib12_executive_local.hex'), os.path.join(builddir, 'mib12_executive_patched.hex'), action='python ../../tools/scripts/patch_start.py %d $SOURCE $TARGET' % app_start)
			highhex = apphex[0]
	else:
		lowhex = apphex[0]
		highhex = env.Command(os.path.join(testdir, 'mib12_app_module_local.hex'), os.path.join(builddir, 'mib12_app_module.hex'), Copy("$TARGET", "$SOURCE"))
	
	outhex = env.merge_mib12_app(os.path.join(outdir, name + '.hex'), [lowhex, highhex])

	outscript = env.Command([os.path.join(outdir, 'test.stc')], [outhex], action=env.Action(build_unittest_script, "Building test script"))

	raw_log_path = os.path.join(outdir, build_logfile_name(env))
	raw_results = env.gpsim_run(raw_log_path, [outscript, outhex]) #include outhex so that scons knows to rerun this command when the hex changes

	#Copy over any addition files that might be needed
	for src, dst in test.copy_files:
		add_file = Command(os.path.join(outdir, dst), src, Copy("$TARGET", "$SOURCE"))
		env.Clean(raw_results, add_file)
		env.Depends(raw_results, add_file)

	#Make sure that the test results explicitly depend on all the additional files that we included
	for src in test.files:
		env.Depends(raw_results, src)

	for dep in test.extra_depends:
		dep_path = os.path.join(outdir, dep)
		env.Depends(raw_results, dep_path)

	#Make the log and status files depend on the contents of all of the test sources so that if we change part of the
	#header, which changes what tests are run, the logs are regenerated.
	formatted_log = env.Command([build_formatted_log_name(env), build_status_name(env)], [raw_results, symtab] + srcfiles, action=env.Action(process_unittest_log, 
		"Processing test log"))

	#Add this unit test to the unit test summary command
	summary_env['TESTS'].append(build_status_name(env))

	#Remember to remove the test directory when cleaning
	#Also add any extra intermediate files that the unit test defines so that 
	#those are cleaned up as well
	env.Clean(outscript, testdir)
	env.Clean(outscript, outdir)
	additional_files = test.get_intermediates(arch)
	for file in additional_files:
		env.Clean(outscript, file)

def build_exec_unittest(test_files, name, chip):
	"""
	Build the unit test described by the source files <test_files>.  Build the 
	MIB12 executive hex file and then a hex file containing the unit test,
	join them together and build gpsim script to execute the test.  Create a combined
	symbol file for the executive and test so that the log file generated by the test
	can be interpreted and addressed mapped to functions.
	"""

	build_unittest(test_files, name, chip, type="executive")

def build_unittest_script(target, source, env):
	"""
	Build a gpsim script to execute this unit test
	"""

	logfile = env['TESTNAME'] + '@' + env['TESTAPPEND'] + '.raw'

	sim = env['TESTCHIP']
	name = env['TESTNAME']
	test = env['TEST']
	arch = env['ARCH']

	sda = arch.property('gpsim_sda')
	scl = arch.property('gpsim_scl')

	extracmds = None

	if 'EXTRACMDS' in env and env['EXTRACMDS'] is not None:
		with open(env['EXTRACMDS'], "r") as f:
			extracmds = f.readlines()

	with open(str(target[0]), "w") as f:
		f.write('processor %s\n' % sim)
		f.write('load s %s\n' % os.path.basename(str(source[0])))
		f.write('break w 0x291, reg(0x291) == 0x00\n')
		f.write('log w %s.ccpr1l\n' % sim)
		f.write('log w %s.ccpr1h\n' % sim)
		f.write("log on '%s'\n\n" % logfile)
		f.write("BreakOnReset = false\n\n")
		
		#Add in all required libraries
		for lib in test.script_additions['libraries']:
			f.write('module library %s\n' % lib)

		#Add in all required modules
		for module,type in test.script_additions['modules'].iteritems():
			f.write('module load %s %s\n' % (type, module))

		#Add in all setup lines:
		for module in test.script_additions['setup_lines'].keys():
			f.write('\n')
			for line in test.script_additions['setup_lines'][module]:
				f.write(line + '\n')

		#Add in sda, scl nodes
		f.write('node sda\n')
		f.write('node scl\n')

		f.write('attach scl %s %s\n' % (scl, ' '.join(test.script_additions['scl_node'])))
		f.write('attach sda %s %s\n' % (sda, ' '.join(test.script_additions['sda_node'])))

		if extracmds is not None:
			for cmd in extracmds:
				f.write(cmd)
			
		#Always run the test and qui when we are done
		f.write('run\n')
		f.write('quit\n')

def process_unittest_log(target, source, env):
	"""
	Source should be the unprocessed log file and the symbol file (stb) for assigning addresses to functions.
	"""
	test = env['TEST']
	symtab = symbols.XC8SymbolTable(str(source[1]))
	lf = log.LogFile(str(source[0]), symtab=symtab)
	lf.save(str(target[0]))

	passed = lf.test_passed(test)
	if passed:
		passed = test.check_output(env['ORIGINAL_ARCH'], str(target[0]))

	test.save_status(str(target[1]), passed)

def build_summary_name():
	return os.path.join('build', 'test', 'output', 'results.txt')

def build_logfile_name(env):
	return env['TESTNAME'] + '@' + env['TESTAPPEND'] + '.raw'

def build_formatted_log_name(env):
	return os.path.join('build', 'test', 'output', 'logs', env['TESTNAME'] + '@' + env['TESTAPPEND'] + '.log')

def build_status_name(env):
	return os.path.join('build', 'test', 'output', 'logs', env['TESTNAME'] + '@' + env['TESTAPPEND'] + '.status')

