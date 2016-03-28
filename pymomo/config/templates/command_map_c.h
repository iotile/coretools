\#ifndef __command_map_c_h__
\#define __command_map_c_h__

\#include <stdint.h>

\#define kAPIMajorVersion		$api_version[0]
\#define kAPIMinorVersion		$api_version[1]

\#define kModuleMajorVersion	$module_version[0]
\#define kModuleMinorVersion	$module_version[1]
\#define kModulePatchVersion	$module_version[2]

\#define kNumCDBCommands		($len($commands))

typedef uint8_t (*cdb_slave_handler)(uint8_t *buffer, unsigned int length, uint8_t *out_buffer, unsigned int *out_length);

typedef struct
{
	cdb_slave_handler	handler;
	uint16_t			command;
	uint16_t			reserved;
} cdb_slave_entry;

\#ifndef NOEXTERNCOMMANDTABLE
extern const cdb_slave_entry cdb_command_map[kNumCDBCommands];
\#endif

\#endif