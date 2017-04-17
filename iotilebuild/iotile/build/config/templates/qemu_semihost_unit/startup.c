#include <stdint.h>

#define WEAK __attribute__ ((weak))
#define ALIAS(f) __attribute__ ((weak, alias (#f)))

void Reset_Handler(void);
void NMI_Handler(void) 			WEAK;
void HardFault_Handler(void) 	WEAK;
void SVC_Handler(void)			WEAK;
void PendSV_Handler(void)		WEAK;
void SysTick_Handler(void)		WEAK;
void Default_Handler(void)		WEAK;

void SPI0_IRQHandler(void) ALIAS(Default_Handler);
void SPI1_IRQHandler(void) ALIAS(Default_Handler);
void UART0_IRQHandler(void) ALIAS(Default_Handler);
void UART1_IRQHandler(void) ALIAS(Default_Handler);
void UART2_IRQHandler(void) ALIAS(Default_Handler);
void I2C1_IRQHandler(void) ALIAS(Default_Handler);
void I2C0_IRQHandler(void) ALIAS(Default_Handler);
void SCT_IRQHandler(void) ALIAS(Default_Handler);
void MRT_IRQHandler(void) ALIAS(Default_Handler);
void CMP_IRQHandler(void) ALIAS(Default_Handler);
void WDT_IRQHandler(void) ALIAS(Default_Handler);
void BOD_IRQHandler(void) ALIAS(Default_Handler);
void FLASH_IRQHandler(void) ALIAS(Default_Handler);
void WKT_IRQHandler(void) ALIAS(Default_Handler);
void ADC_SEQA_IRQHandler(void) ALIAS(Default_Handler);
void ADC_SEQB_IRQHandler(void) ALIAS(Default_Handler);
void ADC_THCMP_IRQHandler(void) ALIAS(Default_Handler);
void ADC_OVR_IRQHandler(void) ALIAS(Default_Handler);
void DMA_IRQHandler(void) ALIAS(Default_Handler);
void I2C2_IRQHandler(void) ALIAS(Default_Handler);
void I2C3_IRQHandler(void) ALIAS(Default_Handler);
void PIN_INT0_IRQHandler(void) ALIAS(Default_Handler);
void PIN_INT1_IRQHandler(void) ALIAS(Default_Handler);
void PIN_INT2_IRQHandler(void) ALIAS(Default_Handler);
void PIN_INT3_IRQHandler(void) ALIAS(Default_Handler);
void PIN_INT4_IRQHandler(void) ALIAS(Default_Handler);
void PIN_INT5_IRQHandler(void) ALIAS(Default_Handler);
void PIN_INT6_IRQHandler(void) ALIAS(Default_Handler);
void PIN_INT7_IRQHandler(void) ALIAS(Default_Handler);

//Symbols defined in linker script
extern void _vStackTop(void);
extern void __code_checksum(void);

__attribute__ ((section(".isr_vector")))
void (* const isr_vectors[])(void) = {
	// Cortex M0+ Defined ISR Vectors
	&_vStackTop, 							// The initial stack pointer
	Reset_Handler,                          // The reset handler
	NMI_Handler,                            // The NMI handler
	HardFault_Handler,                      // The hard fault handler
	0,                                      // Reserved
	0,                                      // Reserved
	0,                                      // Reserved
	&__code_checksum,						// Required checksum for valid user code
	0,                                      // Reserved
	0,                                      // Reserved
	0,                                      // Reserved
	SVC_Handler,                            // SVCall handler
	0,                                      // Reserved
	0,                                      // Reserved
	PendSV_Handler,                         // The PendSV handler
	SysTick_Handler,                        // The SysTick handler

	// LPC824 Defined ISR Vectors
	SPI0_IRQHandler,                         // SPI0 controller
	SPI1_IRQHandler,                         // SPI1 controller
	0,                                       // Reserved
	UART0_IRQHandler,                        // UART0
	UART1_IRQHandler,                        // UART1
	UART2_IRQHandler,                        // UART2
	0,                                       // Reserved
	I2C1_IRQHandler,                         // I2C1 controller
	I2C0_IRQHandler,                         // I2C0 controller
	SCT_IRQHandler,                          // Smart Counter Timer
	MRT_IRQHandler,                          // Multi-Rate Timer
	CMP_IRQHandler,                          // Comparator
	WDT_IRQHandler,                          // Watchdog
	BOD_IRQHandler,                          // Brown Out Detect
	FLASH_IRQHandler,                        // Flash Interrupt
	WKT_IRQHandler,                          // Wakeup timer
	ADC_SEQA_IRQHandler,                     // ADC sequence A completion
	ADC_SEQB_IRQHandler,                     // ADC sequence B completion
	ADC_THCMP_IRQHandler,                    // ADC threshold compare
	ADC_OVR_IRQHandler,                      // ADC overrun
	DMA_IRQHandler,                          // DMA
	I2C2_IRQHandler,                         // I2C2 controller
	I2C3_IRQHandler,                         // I2C3 controller
	0,                                       // Reserved
	PIN_INT0_IRQHandler,                     // PIO INT0
	PIN_INT1_IRQHandler,                     // PIO INT1
	PIN_INT2_IRQHandler,                     // PIO INT2
	PIN_INT3_IRQHandler,                     // PIO INT3
	PIN_INT4_IRQHandler,                     // PIO INT4
	PIN_INT5_IRQHandler,                     // PIO INT5
	PIN_INT6_IRQHandler,                     // PIO INT6
	PIN_INT7_IRQHandler,                     // PIO INT7
};

//*****************************************************************************
// Functions to carry out the initialization of RW and BSS data sections. These
// are written as separate functions rather than being inlined within the
// ResetISR() function in order to cope with MCUs with multiple banks of
// memory.
//*****************************************************************************
void data_init(unsigned int romstart, unsigned int start, unsigned int len) 
{
	unsigned int *pulDest = (unsigned int*) start;
	unsigned int *pulSrc = (unsigned int*) romstart;
	unsigned int loop;
	for (loop = 0; loop < len; loop = loop + 4)
		*pulDest++ = *pulSrc++;
}

__attribute__ ((section(".after_vectors")))
void bss_init(unsigned int start, unsigned int len) 
{
	unsigned int *pulDest = (unsigned int*) start;
	unsigned int loop;
	for (loop = 0; loop < len; loop = loop + 4)
		*pulDest++ = 0;
}

extern uint32_t __data_table_start;
extern uint32_t __bss_table_start;

extern int main(void);
extern void SystemInit(void);

void Reset_Handler(void) 
{
	//
	// Copy the data sections from flash to SRAM.
	//
	uint32_t load_address, store_address, section_length;
	uint32_t *table_address;

	table_address = &__data_table_start;
	load_address = table_address[0];
	store_address = table_address[1];
	section_length = table_address[2];
	data_init(load_address, store_address, section_length);
	
	table_address = &__bss_table_start;
	store_address = table_address[0];
	section_length = table_address[1];
	bss_init(store_address, section_length);

	main();

	while (1)
		;
}

void NMI_Handler(void)
{ 
	while(1)
		;
}

void HardFault_Handler(void)
{ 
	while(1)
		;
}

void SVC_Handler(void)
{ 
	while(1)
		;
}

void PendSV_Handler(void)
{ 
	while(1)
		;
}

void SysTick_Handler(void)
{ 
	while(1)
		;
}

void Default_Handler(void)
{ 
	while(1)
		;
}
