\#ifndef __command_map_c_h__
\#define __command_map_c_h__

\#include <stdint.h>
\#include "cdb_application.h"

\#define kAPIMajorVersion		$api_version[0]
\#define kAPIMinorVersion		$api_version[1]

\#define kModuleMajorVersion	$module_version[0]
\#define kModuleMinorVersion	$module_version[1]
\#define kModulePatchVersion	$module_version[2]

\#define kModuleName			"$name"

\#define kNumCDBCommands		($len($commands))

\#ifndef NOEXTERNAPPINFO
extern const CDBApplicationInfoBlock app_info;
\#endif

\#endif