;command_map.asm
;3 structures defining the features, commands and handlers that we support

\#include "constants.h"
#define __DEFINES_ONLY__
\#include "mib_definitions.h"
#undef __DEFINES_ONLY__

;All MIB endpoints are defined in other files so they must be declared global here.
#for $feat in $features.keys()
	#for $cmd in $features[$feat]
global $cmd.symbol
	#end for
#end for


;High memory command structure for processing mib slave endpoints
PSECT mibblock,global,class=CONST,delta=2
;Module information
retlw 	kModuleHWType		;The HW type that this application module runs on
retlw 	$api_major_version
retlw   $api_minor_version

;Module Name (must be exactly 6 characters long)
;The following instructions ascii-encode this name: '$name'
#for $i in $range(0, 6)
retlw 	$ord($name[$i])
#end for

;Module Version Information
retlw 	$version_major
retlw 	$version_minor
retlw 	$version_patch

retlw 	0x00 			;Checksum to be patched in during build
retlw	kMIBMagicNumber

;MIB Endpoint Information
goto	load_command_map
goto 	load_interface_map


;All of the jump table information is stored here.  On devices with more than one
;memory page, an additional jump table with movlp instructions is created as well
;force that this structure be placed in the same page as mibblock
PSECT mibstructs,global,class=CONST,delta=2,with=mibblock

load_command_map:
movlw LOW (command_map)
movwf FRS0L
movlw HIGH (command_map)
movwf FSR0H
return 

load_interface_map:
movlw LOW (interface_map)
movwf FRS0L
movlw HIGH (interface_map)
movwf FSR0H
return 


mibhandlers:
#if $len($features.keys())>0
brw
#end if

#for $feat in $features.keys()
	#set $cmd_cnt = 0
	#for $cmd in $features[$feat]
	goto $cmd.symbol			; Feature $feat, Command $cmd_cnt
	#set $cmd_cnt = $cmd_cnt + 1
	#end for
#end for
\#endif
