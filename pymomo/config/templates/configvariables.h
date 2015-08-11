\#ifndef __config_variables_h__
\#define __config_variables_h__

\#include <stdint.h>

#for $variable in $configvars.itervalues()
#if $variable.array
extern persistent uint8_t ${variable.name}_length;
extern persistent $variable.type ${variable.name}[$variable.count];
#else
extern persistent $variable.type ${variable.name};
#end if

#end for

\#endif