\#define NOEXTERNAPPINFO
\#include "command_map_c.h"
\#undef NOEXTERNAPPINFO

\#include "config_variables_c.h"

#for $num, $id in $enumerate($sorted($commands.keys()))
uint8_t ${commands[$id].symbol}(uint8_t *buffer, unsigned int length, uint8_t *out_buffer, unsigned int *out_length);
#end for

#if $len($commands) > 0
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
#end if

extern void __image_checksum(void) 	__attribute__ ((weak));

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

	//CDB lookup table sizes
	kNumCDBCommands,
	kNumRequiredConfigs,
	kNumTotalConfigs,

	//Reserved
	0,

\#if kNumTotalConfigs > 0
	cdb_config_map,
\#else
	0,
\#endif

\#if kNumCDBCommands > 0
	cdb_command_map,
\#else
	0,
\#endif

	//Magic number for recognizing CDB block
	kCDBMagicNumber,

	//Reserved for firmware checksum image to be patched in
	(uint32_t)&__image_checksum
};
