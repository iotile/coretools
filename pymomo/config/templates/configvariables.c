\#include <stdint.h>

/* Create structure typedef for all array variables so that their length
 * is guaranteed to be right before the array
 */
#for $variable in $configvars.itervalues()
#if $variable.array
typedef struct
{
	uint8_t length;
	$variable.type data[$variable.count];
} config_${variable.name}_t;

#end if
#end for

#for $variable in $configvars.itervalues()
#if $variable.array
persistent config_${variable.name}_t ${variable.name};
#else
persistent $variable.type ${variable.name};
#end if

#end for