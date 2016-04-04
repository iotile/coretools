\#define NOEXTERNAPPINFO
\#include "command_map_c.h"
\#undef NOEXTERNAPPINFO

#for $num, $id in $enumerate($sorted($commands.keys()))
uint8_t ${commands[$id].symbol}(uint8_t *buffer, unsigned int length, uint8_t *out_buffer, unsigned int *out_length);
#end for

const cdb_slave_entry cdb_command_map[kNumCDBCommands] = 
{
#for $num, $id in $enumerate($sorted($commands.keys()))
	{$commands[$id].symbol, $id, 0}#slurp
#if $num != $len($commands) - 1
,
#else

#end if
#end for
};

const CDBApplicationInfoBlock __attribute__((section (".block.appinfo"))) app_info = {
	//Hardware and API compatibility information
	kModuleHardwareType,
	kAPIMajorVersion,
	kAPIMinorVersion,

	//Module Name
	kModuleName,

	//Module version information
	kModuleMajorVersion,
	kModuleMinorVersion,
	kModulePatchVersion,

	kNumCDBCommands,

	//Reserved bytes
	0,
	0,
	0,
	0,

	cdb_command_map,

	//Magic number for recognizing CDB block
	kCDBMagicNumber,

	//Reserved for firmware checksum image to be patched in
	0
};
