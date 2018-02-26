# This file is copyright Arch Systems, Inc.
# Except as otherwise provided in the relevant LICENSE file, all rights are reserved.

from SCons.Script import *
from SCons.Environment import Environment
import sys
import platform
import os.path
import utilities
import pyparsing
from iotile.build.tilebus.descriptor import TBDescriptor
import struct
from iotile.core.dev.config import ConfigManager
from iotile.core.exceptions import BuildError
from iotile.core.dev.iotileobj import IOTile
from iotile.core.utilities.intelhex import IntelHex
import os
from dependencies import load_dependencies


def build_program(tile, elfname, chip, patch=True):
    """
    Build an ARM cortex executable
    """

    dirs = chip.build_dirs()

    output_name = '%s_%s.elf' % (elfname, chip.arch_name(),)
    output_binname = '%s_%s.bin' % (elfname, chip.arch_name(),)
    patched_name = '%s_%s_patched.elf' % (elfname, chip.arch_name(),)
    patchfile_name = '%s_%s_patchcommand.txt' % (elfname, chip.arch_name(),)
    map_name = '%s_%s.map' % (elfname, chip.arch_name(),)

    VariantDir(dirs['build'], os.path.join('firmware', 'src'), duplicate=0)

    prog_env = setup_environment(chip)
    prog_env['OUTPUT'] = output_name
    prog_env['BUILD_DIR'] = dirs['build']
    prog_env['OUTPUT_PATH'] = os.path.join(dirs['build'], output_name)
    prog_env['OUTPUTBIN'] = os.path.join(dirs['build'], output_binname)
    prog_env['PATCHED'] = os.path.join(dirs['build'], patched_name)
    prog_env['PATCH_FILE'] = os.path.join(dirs['build'], patchfile_name)
    prog_env['PATCH_FILENAME'] = patchfile_name
    prog_env['MODULE'] = elfname

    #Setup all of our dependencies and make sure our output depends on them being built
    tilebus_defs = setup_dependencies(tile, prog_env)

    #Setup specific linker flags for building a program
    ##Specify the linker script
    ###We can find a linker script in one of two places, either in a dependency or in an explicit 'linker' property
    ###First check for a linker script in our dependencies
    ldscripts = reduce(lambda x,y:x+y, [x.linker_scripts() for x in prog_env['DEPENDENCIES']], [])

    # Make sure we don't have multiple linker scripts coming in from dependencies
    if len(ldscripts) > 1:
        raise BuildError("Multiple linker scripts included from dependencies, at most one may be included", linker_scripts=ldscripts)

    #Make sure we don't have a linker script from a dependency and explicity specified
    if len(ldscripts) == 1 and chip.property('linker', None) != None:
        raise BuildError("Linker script specified in dependency and explicitly in module_settings", explicit_script=chip.property('linker'), dependency_script=ldscripts[0])

    if len(ldscripts) == 1:
        ldscript = ldscripts[0]
    else:
        ldscript = utilities.join_path(chip.property('linker'))

    #Find the linker script directory in case it includes other linker scripts in the same directory
    lddir = os.path.abspath(os.path.dirname(ldscript))
    prog_env['LIBPATH'] += [lddir]

    prog_env['LINKFLAGS'].append('-T"%s"' % ldscript)

    ##Specify the output map file
    prog_env['LINKFLAGS'].extend(['-Xlinker', '-Map="%s"' % os.path.join(dirs['build'], map_name)])
    Clean(os.path.join(dirs['build'], output_name), [os.path.join(dirs['build'], map_name)])

    #Compile the TileBus command and config variable definitions
    #Try to use the modern 'tilebus' directory or the old 'cdb' directory
    tbname = os.path.join('firmware', 'src', 'tilebus', prog_env["MODULE"] + ".bus")
    if not os.path.exists(tbname):
        tbname = os.path.join('firmware', 'src', 'cdb', prog_env["MODULE"] + ".cdb")

    compile_tilebus(tilebus_defs + [tbname], prog_env)

    #Compile an elf for the firmware image
    objs = SConscript(os.path.join(dirs['build'], 'SConscript'), exports='prog_env')
    outfile = prog_env.Program(os.path.join(dirs['build'], prog_env['OUTPUT']), objs)

    if patch:
        #Create a patched ELF including a proper checksum
        ## First create a binary dump of the program flash
        outbin = prog_env.Command(prog_env['OUTPUTBIN'], os.path.join(dirs['build'], prog_env['OUTPUT']), "arm-none-eabi-objcopy -O binary $SOURCES $TARGET")

        ## Now create a command file containing the linker command needed to patch the elf
        outhex = prog_env.Command(prog_env['PATCH_FILE'], outbin, action=prog_env.Action(checksum_creation_action, "Generating checksum file"))

        ## Next relink a new version of the binary using that patch file to define the image checksum
        patch_env = prog_env.Clone()
        patch_env['LINKFLAGS'].append(['-Xlinker', '@%s' % patch_env['PATCH_FILE']])

        patched_file = patch_env.Program(prog_env['PATCHED'], objs)
        patch_env.Depends(patched_file, [os.path.join(dirs['build'], output_name), patch_env['PATCH_FILE']])

        prog_env.Depends(os.path.join(dirs['build'], output_name), [ldscript])

        prog_env.InstallAs(os.path.join(dirs['output'], output_name), os.path.join(dirs['build'], patched_name))
    else:
        prog_env.InstallAs(os.path.join(dirs['output'], output_name), outfile)

    prog_env.InstallAs(os.path.join(dirs['output'], map_name), os.path.join(dirs['build'], map_name))

    return os.path.join(dirs['output'], output_name)

def build_library(tile, libname, chip):
    """
    Build a static ARM cortex library
    """

    dirs = chip.build_dirs()

    output_name = '%s_%s.a' % (libname, chip.arch_name())

    #Support both firmware/src and just src locations for source code
    if os.path.exists('firmware'):
        VariantDir(dirs['build'], os.path.join('firmware', 'src'), duplicate=0)
    else:
        VariantDir(dirs['build'], 'src', duplicate=0)

    library_env = setup_environment(chip)
    library_env['OUTPUT'] = output_name
    library_env['OUTPUT_PATH'] = os.path.join(dirs['build'], output_name)
    library_env['BUILD_DIR'] = dirs['build']

    # Check for any dependencies this library has
    tilebus_defs = setup_dependencies(tile, library_env)

    #Create header files for all tilebus config variables and commands that are defined in ourselves
    #or in our dependencies
    tilebus_defs += tile.tilebus_definitions()
    compile_tilebus(tilebus_defs, library_env, header_only=True)

    SConscript(os.path.join(dirs['build'], 'SConscript'), exports='library_env')

    library_env.InstallAs(os.path.join(dirs['output'], output_name), os.path.join(dirs['build'], output_name))

    #See if we should copy any files over to the output:
    for src,dst in chip.property('copy_files', []):
        srcpath = os.path.join(*src)
        destpath = os.path.join(dirs['output'], dst)
        library_env.InstallAs(destpath, srcpath)

    return os.path.join(dirs['output'], output_name)

def setup_environment(chip):
    """
    Setup the SCons environment for compiling arm cortex code
    """

    config = ConfigManager()

    #Make sure we never get MSVC settings for windows since that has the wrong command line flags for gcc
    if platform.system() == 'Windows':
        env = Environment(tools=['mingw'], ENV=os.environ)
    else:
        env = Environment(tools=['default'], ENV=os.environ)

    env['INCPREFIX'] = '-I"'
    env['INCSUFFIX'] = '"'
    env['CPPPATH'] = chip.includes()
    env['ARCH'] = chip

    #Setup Cross Compiler
    env['CC']       = 'arm-none-eabi-gcc'
    env['AS']       = 'arm-none-eabi-gcc'
    env['LINK']     = 'arm-none-eabi-gcc'
    env['AR']       = 'arm-none-eabi-ar'
    env['RANLIB']   = 'arm-none-eabi-ranlib'

    #AS command line is by default setup for call as directly so we need to modify it to call via *-gcc to allow for preprocessing
    env['ASCOM'] = "$AS $ASFLAGS -o $TARGET -c $SOURCES"

    # Setup nice display strings unless we're asked to show raw commands
    if not config.get('build:show-commands'):
        env['CCCOMSTR'] = "Compiling $TARGET"
        env['ARCOMSTR'] = "Building static library $TARGET"
        env['RANLIBCOMSTR'] = "Indexing static library $TARGET"
        env['LINKCOMSTR'] = "Linking $TARGET"

    #Setup Compiler Flags
    env['CCFLAGS'] = chip.combined_properties('cflags')
    env['LINKFLAGS'] = chip.combined_properties('ldflags')
    env['ARFLAGS'].append(chip.combined_properties('arflags')) #There are default ARFLAGS that are necessary to keep
    env['ASFLAGS'].append(chip.combined_properties('asflags'))

    #Add in compile tile definitions
    defines = utilities.build_defines(chip.property('defines', {}))
    env['CCFLAGS'].append(defines)

    #Setup Target Architecture
    env['CCFLAGS'].append('-mcpu=%s' % chip.property('cpu'))
    env['ASFLAGS'].append('-mcpu=%s' % chip.property('cpu'))
    env['LINKFLAGS'].append('-mcpu=%s' % chip.property('cpu'))

    #Initialize library paths (all libraries are added via dependencies)
    env['LIBPATH'] = []
    env['LIBS'] = []

    return env

def toposort_dependencies(env):
    from toposort import toposort
    liborder = {x.name: set(map(lambda x: x['name'], x.dependencies)) for x in env['DEPENDENCIES']}
    liborder = list(toposort(liborder))

    sorted_deps = {}
    sort_count = 0
    for stage in liborder:
        for obj in stage:
            sorted_deps[obj] = sort_count
            sort_count += 1

    return sorted_deps

def setup_dependencies(tile, env):
    # Check for any dependencies this library has
    dep_nodes = load_dependencies(tile, env)
    env.Depends(env['OUTPUT_PATH'], dep_nodes)

    ## Add in all include directories, library directories and libraries from dependencies
    dep_incs = reduce(lambda x,y:x+y, [x.include_directories() for x in env['DEPENDENCIES']], [])
    lib_dirs = reduce(lambda x,y:x+y, [x.library_directories() for x in env['DEPENDENCIES']], [])
    tilebus_defs = reduce(lambda x,y:x+y, [x.tilebus_definitions() for x in env['DEPENDENCIES']], [])

    env['CPPPATH'] += map(lambda x: '#' + x, dep_incs)
    env['LIBPATH'] += lib_dirs

    #We need to add libraries in reverse dependency order so that gcc resolves symbols among the libraries
    #correctly
    lib_order = toposort_dependencies(env)
    libs = [(x.name, x.libraries()) for x in env['DEPENDENCIES']]

    libs.sort(key=lambda x: lib_order[x[0]], reverse=True)


    for lib_parent, lib_list in libs:
        env['LIBS'] += lib_list

    return tilebus_defs

def compile_tilebus(files, env, outdir=None, header_only=False):
    """
    Given a path to a *.cdb file, process it and generate c tables and/or headers containing the information.
    """

    if outdir is None:
        dirs = env["ARCH"].build_dirs()
        outdir = dirs['build']

    cmdmap_c_path = os.path.join(outdir, 'command_map_c.c')
    cmdmap_h_path = os.path.join(outdir, 'command_map_c.h')
    config_c_path = os.path.join(outdir, 'config_variables_c.c')
    config_h_path = os.path.join(outdir, 'config_variables_c.h')

    if header_only:
        return env.Command([cmdmap_h_path, config_h_path], files, action=env.Action(tb_h_file_creation, "Creating header files from TileBus definitions"))
    else:
        env['MIBFILE'] = '#' + cmdmap_c_path
        return env.Command([cmdmap_c_path, cmdmap_h_path, config_c_path, config_h_path], files, action=env.Action(tb_c_file_creation, "Compiling TileBus commands and config variables"))


def tb_c_file_creation(target, source, env):
    """
    Compile tilebus file into a .h/.c pair for compilation into an ARM object
    """

    files = [str(x) for x in source]

    try:
        desc = TBDescriptor(files)
    except pyparsing.ParseException as e:
        raise BuildError("Could not parse tilebus file", parsing_exception=e)

    block = desc.get_block()
    block.render_template(block.CommandFileTemplate, out_path=str(target[0]))
    block.render_template(block.CommandHeaderTemplate, out_path=str(target[1]))
    block.render_template(block.ConfigFileTemplate, out_path=str(target[2]))
    block.render_template(block.ConfigHeaderTemplate, out_path=str(target[3]))


def tb_h_file_creation(target, source, env):
    """
    Compile tilebus file into only .h files corresponding to config variables for inclusion in a library
    """

    files = [str(x) for x in source]

    try:
        desc = TBDescriptor(files)
    except pyparsing.ParseException as e:
        raise BuildError("Could not parse tilebus file", parsing_exception=e)

    block = desc.get_block(config_only=True)
    block.render_template(block.CommandHeaderTemplate, out_path=str(target[0]))
    block.render_template(block.ConfigHeaderTemplate, out_path=str(target[1]))


def checksum_creation_action(target, source, env):
    """
    Create a linker command file for patching an application checksum into a firmware image
    """

    # Important Notes:
    # There are apparently many ways to calculate a CRC-32 checksum, we use the following options
    # Initial seed value prepended to the input: 0xFFFFFFFF
    # Whether the input is fed into the shift register least-significant bit or most-significant bit first: LSB
    # Whether each data word is inverted: No
    # Whether the final CRC value is inverted: No
    # *These settings must agree between the executive and this function*

    import crcmod
    crc32_func = crcmod.mkCrcFun(0x104C11DB7, initCrc=0xFFFFFFFF, rev=False, xorOut=0)

    with open(str(source[0]), 'rb') as f:
        data = f.read()

        #Ignore the last four bytes of the file since that is where the checksum will go
        data = data[:-4]

        #Make sure the magic number is correct so that we're dealing with an actual firmware image
        magicbin = data[-4:]
        magic, = struct.unpack('<L', magicbin)

        if magic != 0xBAADDAAD:
            raise BuildError("Attempting to patch a file that is not a CDB binary or has the wrong size", reason="invalid magic number found", actual_magic=magic, desired_magic=0xBAADDAAD)

        #Calculate CRC32 in the same way as its done in the target microcontroller
        checksum = crc32_func(data) & 0xFFFFFFFF

    with open(str(target[0]), 'w') as f:
        # hex strings end with L on windows and possibly some other systems
        checkhex = hex(checksum)
        if checkhex[-1] == 'L':
            checkhex = checkhex[:-1]

        f.write("--defsym=__image_checksum=%s\n" % checkhex)

def merge_hex_executables(target, source, env):
    """
    Combine all hex files into a singular executable file
    """
    output_name = (str(target[0]))

    hex_final = IntelHex()
    for image in source:
        file = str(image)
        root, ext = os.path.splitext(file)
        file_format = ext[1:]
        if file_format == 'elf':
            file = root + '.hex'
        hex_data = IntelHex(file)

        #merge will throw errors on mismatched Start Segment Addresses, which we don't need
        #See <https://stackoverflow.com/questions/26295776/what-are-the-intel-hex-records-type-03-or-05-doing-in-ihex-program-for-arm>
        hex_data.start_addr = None
        hex_final.merge(hex_data, overlap='error')

    with open(output_name, 'wb') as f:
        hex_final.write_hex_file(f)