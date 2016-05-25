\#include <stdint.h>
\#include "config_variables.h"
/* Create structure typedef for all array variables so that their length
 * is guaranteed to be right before the array
 */

#for $variable in $configvars.itervalues()
persistent config_${variable.name}_t ${variable.name};
#end for