\#ifndef __config_variables_c_h__
\#define __config_variables_c_h__

\#include <stdint.h>
\#include <stdbool.h>
\#include "cdb_application.h"

\#define kNumRequiredConfigs	($len($filter(lambda x: x['required'], $configs.itervalues())))
\#define kNumTotalConfigs 		($len($configs))

#for $variable in $configs.itervalues()
#if not $variable.array
#continue
#end if
typedef struct
{
	uint16_t 		length;
	uint16_t		reserved;
	$variable.type 			data[$variable.count];
} config_${variable.name}_t;

#end for

\#ifndef NOEXTERNAPPINFO
#for $variable in $configs.itervalues()
#if $variable.array
extern config_${variable.name}_t $variable.name;
#else
extern $variable.type $variable.name;
#end if
#end for

#if $len($configs) > 0
extern const cdb_config_entry cdb_config_map[kNumTotalConfigs];
#end if

\#endif

\#endif
