/*
 * Linker Script for Generic ARM Cortex semihosted QEMU unit tests
 */

__ram_size 	 =	4k;
__flash_size =	32k;

/*
 * Define symbols for the start and end of each region
 */

__flash_start 	= 0x0;
__flash_end 	= __flash_start + __flash_size;
__ram_start 	= 0x20000000;
__ram_end 		= __ram_start + __ram_size;


MEMORY
{
	flash 	(rx) 	: ORIGIN = 0x0, 						LENGTH = __flash_size
 	ram 	(rwx) 	: ORIGIN = 0x20000000, 					LENGTH = __ram_size
}



/*
 * Per the LPC824 User Manual, IAP ROM firmware uses the 32 high bytes of RAM so we need to
 * make sure that does not contain stack frames, otherwise we could corrupt the stack.
 */
__stack_start = __ram_end;

ENTRY(Reset_Handler)

SECTIONS
{
	/*
	 * Flash Sections
	 */

	.text : ALIGN(4)
	{
		FILL(0xff)

		__isr_vectors_start__ = ABSOLUTE(.);
		KEEP(*(.isr_vector))

		/* 
		 * Section Table for loading initialized values into RAM
		 * and clearing uninitialized values to zero.
		 */

		. = ALIGN(4); 
		__section_table_start = ABSOLUTE(.);
		
		__data_table_start = ABSOLUTE(.);
		LONG(LOADADDR(.data));
		LONG(ADDR(.data));
		LONG(SIZEOF(.data));
		__data_table_end = ABSOLUTE(.);
		
		__bss_table_start = ABSOLUTE(.);
		LONG(ADDR(.bss));
		LONG(SIZEOF(.bss));
		__bss_section_table_end = ABSOLUTE(.);

		__section_table_end = ABSOLUTE(.);

		. = ALIGN(4);
		__isr_vectors_end__ = ABSOLUTE(.);
	} > flash =0xFF

	.text : ALIGN(4)
	{
		*(.text*)
		*(.rodata .rodata.* .constdata .constdata.*)

		. = ALIGN(4);
	} > flash =0xFF

    /*
     * RAM Sections
     * 		.data contains all initialized variables that is copied to ram
     *		.bss contains all unitialized variables that are cleared to 0
     * 		.noinit contains all unitialized variables that should not be cleared
     */

	.data : ALIGN(4)
	{
		FILL(0xff)
		
		*(vtable)
		*(.ramfunc*)
		*(.data*)

		. = ALIGN(4);

		__used_flash = ABSOLUTE(.) - __flash_start;
	} >ram AT >flash

	.bss : ALIGN(4)
	{
		*(.bss*)
		*(COMMON)
		. = ALIGN(4) ;
	} > ram

	.noinit (NOLOAD): ALIGN(4)
	{
		*(.noinit*) 
		. = ALIGN(4);

		__used_ram = ABSOLUTE(.) - __ram_start;
	} > ram

	PROVIDE(_vStackTop = __stack_start);
	PROVIDE(__code_checksum = 0 - 
	(_vStackTop
	+ Reset_Handler + 1
	+ NMI_Handler + 1 
	+ HardFault_Handler + 1
	));
}