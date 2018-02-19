#define NOEXTERNAPPINFO
#include "command_map_c.h"
#undef NOEXTERNAPPINFO

#include "config_variables_c.h"

/* 
 * RPC Handler Prototypes
 *
 * These C functions must be defined in your embedded firmware
 * and the linker will put pointers to them in the global command
 * map file for your program so that they can be called externally
 */
{% for id, command in commands | dictsort %}
uint8_t {{command.symbol}}(uint8_t *buffer, unsigned int length, uint8_t *out_buffer, unsigned int *out_length);
{% endfor %}

{% if commands | length > 0 %}
const cdb_slave_entry cdb_command_map[kNumCDBCommands] = 
{
{% for id, command in commands | dictsort %}
    {{'{'}}{{command.symbol}}, {{"0x%04X" % id}}, 0}{%+ if not loop.last %},
{% endif %}
{% endfor %}

};
{% endif %}

extern void __image_checksum(void)  __attribute__ ((weak));

const CDBApplicationInfoBlock __attribute__((section (".block.appinfo"))) app_info = 
{
    //Hardware and API compatibility information
    kModuleHardwareType,
    kAPIMajorVersion,
    kAPIMinorVersion,

    //Module Name
    kModuleName,

    //Module version information
    kModuleMajorVersion,
    kModuleMinorVersion,
    kModulePatchVersion,

    //CDB lookup table sizes
    kNumCDBCommands,
    kNumRequiredConfigs,
    kNumTotalConfigs,

    //Reserved
    0,

{% if configs | length > 0 %}
    cdb_config_map,
{% else %}
    0,
{% endif %}

{% if commands | length > 0 %}
    cdb_command_map,
{% else %}
    0,
{% endif %}

    //Magic number for recognizing CDB block
    kCDBMagicNumber,

    //Reserved for firmware checksum image to be patched in
    (uint32_t)&__image_checksum
};
