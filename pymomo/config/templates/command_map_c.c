\#define NOEXTERNCOMMANDTABLE
\#include "command_map_c.h"
\#undef NOEXTERNCOMMANDTABLE

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
