\#define NOEXTERNAPPINFO
\#include "config_variables_c.h"
\#undef NOEXTERNAPPINFO

\#include "cdb_application.h"

/* Required Config Variables */
#for $variable in $configs.itervalues()
#if $variable.required == False
#continue
#end if 
#if $variable.array
config_${variable.name}_t __attribute__((section(".required_config"))) $variable.name;
#else
$variable.type __attribute__((section(".required_config"))) $variable.name;
#end if
#end for

/* Optional Config Variables */
#for $variable in $configs.itervalues()
#if $variable.required
#continue
#end if 
#if $variable.array
config_${variable.name}_t __attribute__((section(".optional_config"))) $variable.name = {$variable.total_size, 0, $variable.default_value};
#else
$variable.type __attribute__((section(".optional_config"))) $variable.name = $variable.default_value;
#end if
#end for

/* Config Variable Map */

#if $len($configs) > 0
const cdb_config_entry cdb_config_map[kNumTotalConfigs] = 
{
#set $reqkeys = $filter(lambda x: $configs[x]['required'], $configs.iterkeys())
#set $optkeys = $filter(lambda x: not $configs[x]['required'], $configs.iterkeys())
#for $num, $id in $enumerate($sorted($reqkeys))
	{&$configs[$id].name, $id, $configs[$id].total_size, $int($configs[$id].array)}#slurp
#if $num != $len($configs) - 1
,
#else

#end if
#end for
#for $num, $id in $enumerate($sorted($optkeys))
	{&$configs[$id].name, $id, $configs[$id].total_size, $int($configs[$id].array)}#slurp
#if $num != $len($configs) - 1 - $len($reqkeys)
,
#else

#end if
#end for
};
#end if
