;command_map.asm
;3 structures defining the features, commands and handlers that we support

\#include "protocol_defines.h"
\#include "mib12_block.h"
\#include <xc.inc>

;All MIB endpoints are defined in other files so they must be declared global here.
#for $cmd in $commands.values()
global $cmd.symbol
#end for

;All Config Variables are defined in other files so they must be declared global here
#for $var in $configs.values()
global _$var.name
#end for

;All Default Config Variable Values (if any) are defined in other files so they must be declared global here
#for $var in $configs.values()
#if $var.required == False
global ${var.name}_default
#end if
#end for


;High memory command structure for processing mib slave endpoints
PSECT mibblock,global,class=CONST,delta=2

\#if kFlashRowSize == 32
;On 32 word pages, make sure the rest of the mib block page is filled.
#for $i in $xrange(0,16)
retlw 0x00
#end for
\#elif kFlashRowSize != 16
\#error "The flash row size must be either 32 or 16 for the command_map template to work"
\#endif

;Module information
retlw 	kModuleHWType		;The HW type that this application module runs on
retlw 	$api_version[0]	;Compatible Executive API Major Version
retlw   $api_version[1] ;Compatible Executive API Minor Version

;Module Name (must be exactly 6 characters long)
;The following instructions ascii-encode this name: '$name'
#for $i in $range(0, 6)
retlw 	$ord($name[$i])
#end for

;Module Version Information
retlw 	$module_version[0] ;Module Major Version
retlw 	$module_version[1] ;Module Minor Version
retlw 	$module_version[2] ;Module Patch Version

retlw 	0x00 			;Checksum to be patched in during build
retlw	kMIBMagicNumber ;MIB magic number

;MIB endpoint, interfaces and configuration information
goto	app_information

;Reserved, must be zero.
retlw 	0x00


;These generated functions return the command map and interface map
;locations, which can be located at an RAM or ROM location.
PSECT mibstructs,global,class=CODE,delta=2,with=mibblock

;Given a value in W, return the appropriate information by loading it into FSR0
;0: selects the MIB endpoint table
;1: selects the supported interface list
;2: selects the configuration variable metadata list
;3: selects the configuration variable address list
app_information:
andlw 0b11
brw
goto load_command_map
goto load_interface_map
goto load_config_metadata_map
goto load_config_address_map

load_command_map:
movlw (command_map & 0xFF)
movwf FSR0L
movlw ((command_map >> 8) | (1 << 7))
movwf FSR0H
return 

load_interface_map:
movlw (interface_map & 0xFF)
movwf FSR0L
movlw ((interface_map >> 8) | (1 << 7))
movwf FSR0H
return 

load_config_metadata_map:
movlw (config_metadata_map & 0xFF)
movwf FSR0L
movlw ((config_metadata_map >> 8) | (1 << 7))
movwf FSR0H
return 

load_config_address_map:
movlw (config_address_map & 0xFF)
movwf FSR0L
movlw ((config_address_map >> 8) | (1 << 7))
movwf FSR0H
return 

;Command Map Table
PSECT mib_command_map, global, class=CONST, delta=2

command_map:
#for $id in $sorted($commands.keys())
#set $idlow = $id & 0xFF
#set $idhigh = $id >> 8
retlw $idlow
retlw $idhigh
retlw $commands[$id].symbol & 0xFF
retlw ($commands[$id].symbol >> 8) & 0xFF

#end for
;Sentinel value
retlw 0xFF
retlw 0xFF
retlw 0xFF
retlw 0xFF

interface_map:
#for $iface in $sorted($interfaces)
#set $id1 = $iface & 0xFF
#set $id2 = ($iface >> 8) & 0xFF
#set $id3 = ($iface >> 16) & 0xFF
#set $id4 = ($iface >> 24) & 0xFF
retlw $id1
retlw $id2
retlw $id3
retlw $id4

#end for
;Sentinel value
retlw 0xFF
retlw 0xFF
retlw 0xFF
retlw 0xFF

;Defined configuration variables in this module
;Format is:
;Byte 1: Low byte of ID
;Byte 2: High byte of ID
;Byte 3: Flags organized as:
;  - Bits 0-5: The offset of this entry in the list
;  - Bit 6: Whether this variable has a default value
;  - Bit 7: Whether this variable is a buffer (1) or has a fixed length (0)
config_metadata_map:
#for $id, $var in sorted($configs.iteritems(), key=lambda x: $x[1].flags & 0b00111111)
#set $id1 = $id & 0xFF
#set $id2 = ($id >> 8) & 0xFF
;Variable $var.name
retlw $id1
retlw $id2
retlw $var.flags
retlw $var.total_size

#end for
retlw 0xFF
retlw 0xFF
retlw 0xFF
retlw 0xFF

config_address_map:
#for $id, $var in sorted($configs.iteritems(), key=lambda x: $x[1].flags & 0b00111111)
retlw (_$var.name & 0xFF)
retlw (_$var.name >> 8) & 0xFF
#if $var.required
retlw 0xFF
retlw 0xFF
#else
retlw (${var.name}_default & 0xFF)
retlw ((${var.name}_default >> 8) | (1 << 7))
#end if

#end for
retlw 0xFF
retlw 0xFF
retlw 0xFF
retlw 0xFF

