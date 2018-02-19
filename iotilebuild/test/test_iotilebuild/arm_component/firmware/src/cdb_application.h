#ifndef __cdb_application_h__
#define __cdb_application_h__

#include <stdint.h>

#define kCDBModuleNameLength    6
#define kCDBMagicNumber         0xBAADDAAD
#define kModuleHardwareType     1

//Slave RPC Handler 
typedef uint8_t (*cdb_slave_handler)(uint8_t *buffer, unsigned int length, uint8_t *out_buffer, unsigned int *out_length);

//RPC handler table entry format
typedef struct
{
    cdb_slave_handler   handler;
    uint16_t            command;
    uint16_t            reserved;
} cdb_slave_entry;

//Entry for specifying a configuration variable
typedef struct
{
    void                *variable;
    uint16_t            id;
    uint16_t            size: 15;
    uint16_t            variable_size: 1;
} cdb_config_entry;

typedef struct
{
    uint32_t            section_size;
    uint32_t            vars[];
} cdb_optional_variables_table_t;

/*
 * Information block about CDB compatile application firmware image
 */
typedef struct
{
    uint8_t                 hardware_type;
    uint8_t                 api_major_version;
    uint8_t                 api_minor_version;

    char                    name[kCDBModuleNameLength];

    uint8_t                 module_major_version;
    uint8_t                 module_minor_version;        
    uint8_t                 module_patch_version;

    uint8_t                 num_slave_commands;
    uint8_t                 num_required_configs;
    uint8_t                 num_total_configs;
    
    uint8_t                 reserved;

    const cdb_config_entry  *config_variables;
    const cdb_slave_entry   *slave_handlers;        

    uint32_t                magic_number;
    uint32_t                firmware_checksum;
} CDBApplicationInfoBlock;

#endif