\#include <stdint.h>

#for $variable in $configvars.itervalues()
#if $variable.array
persistent uint8_t ${variable.name}_length;
persistent $variable.type ${variable.name}[$variable.count];
#else
persistent $variable.type ${variable.name};
#end if

#end for