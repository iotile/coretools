;command_map.asm
;3 structures defining the features, commands and handlers that we support

\#include "constants.h"
#define __DEFINES_ONLY__
\#include "mib_definitions.h"
#undef __DEFINES_ONLY__

jumpm MACRO name,dest
name:
	pagesel(dest)
	goto  dest && ((1<<11) - 1)
	
ENDM

;All MIB endpoints are defined in other files so they must be declared global here.
#for $feat in $features.keys()
	#for $cmd in $features[$feat]
global $cmd.symbol
	#end for
#end for


;High memory command structure for processing mib slave endpoints
;Specify a max size so that we can make sure nothing funny is happening with the psect
PSECT mibblock,global,class=CONST,delta=2
;Module information
retlw 	kModuleHWType			;The HW type that this application module runs on
retlw 	$module_type			;ModuleType
retlw 	1<<4 | ($flags & 0xFF) 	;Nibble for MIB Revision, Nibble for Module Flags

;Module Name (must be exactly 7 characters long)
;Following instructions ascii-encode this name: '$name'
#for $i in $range(0, $len($name))
retlw 	$ord($name[$i])
#end for

;MIB endpoint information
retlw 	$num_features
goto 	mibfeatures
goto 	mibcommands
goto 	mibspecs
goto 	mibhandlers
retlw	kMIBMagicNumber


;All of the jump table information is stored here.  On devices with more than one
;memory page, an additional jump table with movlp instructions is created as well
;force that this structure be placed in the same page as mibblock
PSECT mibstructs,global,class=CONST,delta=2,with=mibblock

;On paged memory devices, the redirection table with movlp protection commands is stored here
;on devices that have 2K or less of RAM this is not needed.
\#ifdef kMultipageDevice
#set global $intermeds = []
#set global $inter_n = 0

#def next_placeholder($symbol)
#set $p = "inter_%d" % $inter_n
$intermeds.append($p)
#set global $inter_n += 1
jumpm $p, $symbol #slurp
#end def
;Redirection jump table #slurp
#for $feat in $features.keys()
	#for $cmd in $features[$feat]
	#set $cmd_cnt = 0
$next_placeholder($cmd.symbol) ; Feature $feat, Command $cmd_cnt #slurp
	#set $cmd_cnt = $cmd_cnt + 1
	#end for
#end for


mibhandlers:
#if $len($features.keys())>0
brw
#end if

#for $j in $intermeds
	goto $j
#end for

\#else
;On nonpaged memory devices we can safely just jump to the symbols directly and save memory
;and time
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


mibfeatures:
#if $len($features.keys())>0
brw
#end if

#for $feat in $features.keys()
	retlw $feat
#end for

#set $cmd_cnt = 0
mibcommands:
#if $len($features.keys())>0
brw
#end if
#for $feat in $features.keys()
	retlw $cmd_cnt
	#set $cmd_cnt = $cmd_cnt + $len($features[$feat])
#end for

#if $len($features.keys())>0
	retlw $cmd_cnt
#end if

mibspecs:
#if $len($features.keys())>0
brw
#end if
#for $feat in $features.keys()
	#for $cmd in $features[$feat]
	retlw $cmd.spec
	#end for
#end for