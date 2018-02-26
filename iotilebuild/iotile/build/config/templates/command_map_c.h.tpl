#ifndef __command_map_c_h__
#define __command_map_c_h__

#include <stdint.h>
#include "cdb_application.h"

#define kAPIMajorVersion    {{ versions.api[0] }}
#define kAPIMinorVersion    {{ versions.api[1] }}

#define kModuleMajorVersion {{ versions.module[0] }}
#define kModuleMinorVersion {{ versions.module[1] }}
#define kModulePatchVersion {{ versions.module[2] }}

#define kModuleName         "{{ short_name }}"

#define kNumCDBCommands     ({{ commands | length }})

#ifndef NOEXTERNAPPINFO
extern const CDBApplicationInfoBlock app_info;
#endif

#endif