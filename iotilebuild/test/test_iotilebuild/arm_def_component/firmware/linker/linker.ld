/*
 * Linker Script for NXP LPC824 Cortex M0+ Processor
 */

__flash_size = 32K;
__ram_size = 8K;
__exec_size = 6K;
__exec_ram_size = 128;

__api_size	= 64;
__info_size = 32;
__api_start = __exec_size - __api_size - __info_size;

__app_start = __exec_size;

__flash_start 	= 0x0;
__flash_end 	= __flash_size;

__ram_start 	= 0x10000000 + __exec_ram_size;
__ram_end 		= __ram_start + __ram_size - __exec_ram_size;

MEMORY
{
	app_flash	(rx)	: ORIGIN = __exec_size, 				LENGTH = __flash_size - __exec_size - __info_size
	app_info 	(rx)	: ORIGIN = __flash_size - __info_size,	LENGTH = __info_size
 	app_ram 	(rwx) 	: ORIGIN = __ram_start, 				LENGTH = __ram_size - __exec_ram_size
}

/*
 * Define symbols for the start and end of each region
 */

ENTRY(Reset_Handler)

SECTIONS
{
	/*
	 * Flash Sections
	 */

	 /*
	  * NB, this .text section must remain the same as the initial section in the lpc824 executive since
	  * we need to know the offset of section .optional_config.
	  */
	.text.isr_region : ALIGN(4)
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
		
		/* This needs to be placed directly after the section tables and right before .optional_config */
		LONG(SIZEOF(.optional_config));
	} > app_flash =0xFF

	/*
	 * Place config variables with default values directly after isr table so that we know
	 * where they are and can copy them into place. 
	 */
	.optional_config : ALIGN(4)
    {
    	FILL(0xff)
    	__optional_config_start = ABSOLUTE(.);
    	

    	KEEP(*(.optional_config))

    	. = ALIGN(4);
    	__optional_config_end = ABSOLUTE(.);
    } >app_ram AT >app_flash =0xFF

   	/*
   	 * Place all of the code in flash
   	 */
	.text : ALIGN(4)
	{
		*(.text*)
		*(.rodata .rodata.* .constdata .constdata.*)

		. = ALIGN(4);
	} > app_flash =0xFF

	/*
	 * Used for stack unwinding tables
	 */
	.ARM.edidx : ALIGN(4)
	{
		__exidx_start = .;
		*(.ARM.exidx)
		__exidx_end = .;

		. = ALIGN(4);
	} > app_flash =0xFF

	/*
	 * Include the application information block at the end of the image
	 */
	.block.appinfo : ALIGN(4)
	{
		KEEP(*(.block.appinfo))
	} > app_info

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
	} >app_ram AT >app_flash

	.fill : ALIGN(4)
	{
		__fill_start = ABSOLUTE(.);

		FILL(0xFF);

		. = . + __flash_size - __fill_start - 1 - __info_size;

		BYTE(0xFF);
	} > app_flash

	.bss : ALIGN(4)
	{
		*(.bss*)
		*(COMMON)
		. = ALIGN(4) ;
	} > app_ram

	.noinit (NOLOAD): ALIGN(4)
	{
		*(.noinit*)
		*(.required_config*)
		. = ALIGN(4);

		__used_ram = ABSOLUTE(.) - __ram_start;
	} > app_ram

	

	PROVIDE(_vStackTop = __ram_end);
	PROVIDE(__code_checksum = 0 - 
	(_vStackTop
	+ Reset_Handler + 1
	+ NMI_Handler + 1 
	+ HardFault_Handler + 1
	));

	PROVIDE(__optional_config_size = __optional_config_end - __optional_config_start);
	/* The location of the application info block if it exists */
	PROVIDE(__app_info_start = __flash_end - __info_size);
	PROVIDE(__application_start = __app_start);
	PROVIDE(__application_end = __flash_end);

	/* The location of the executive api block */
	PROVIDE(__exec_api = __api_start);
}