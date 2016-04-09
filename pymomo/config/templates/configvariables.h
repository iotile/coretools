\#ifndef __config_variables_h__
\#define __config_variables_h__

\#include <stdint.h>

#for $variable in $configvars.itervalues()
typedef struct
{
	uint8_t length;
	$variable.type data[$variable.count];
} config_${variable.name}_t;

#end for

#for $variable in $configvars.itervalues()
extern persistent config_${variable.name}_t ${variable.name};
#end for

\#endif
