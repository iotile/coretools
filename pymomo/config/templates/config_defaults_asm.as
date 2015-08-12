\#include <xc.inc>

PSECT config_defaults, global, class=CONST, delta=2

#for $variable in $configvars.itervalues()
#if not $variable.required
global ${variable.name}_default
#end if
#end for

#for $variable in $configvars.itervalues()
#if not $variable.required
${variable.name}_default:
#set $length = $len($variable.default_value)
retlw $length ; Variable Length $length
#for $byte in $variable.default_value
retlw $byte
#end for
#end if

#end for