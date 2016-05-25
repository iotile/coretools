;startup.as

\#include <xc.inc>


global _main, _task,_initialize,_interrupt_handler,start,intlevel1

PSECT reset_vec,global,class=CODE,delta=2
start:
goto _initialize
goto _interrupt_handler
goto _task

intlevel1:

PSECT powerup,global,class=CODE,delta=2

PSECT functab,global,class=CODE,delta=2

PSECT config,global,class=CODE,delta=2

PSECT idloc,global,class=CODE,delta=2

PSECT eeprom_data,global,class=CODE,delta=2