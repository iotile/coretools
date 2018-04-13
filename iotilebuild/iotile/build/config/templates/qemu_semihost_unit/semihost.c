#include "semihost.h"

/*!\brief Trigger a semihosting service call on qemu
 */

void __attribute__((noinline)) svc(volatile unsigned int arg0, volatile void *arg1)
{
	(void)arg0;
	(void)arg1;

    asm volatile(
        "bkpt 0xab"
        :
        :
        : "r0", "r1"
    );
}

void qemu_semihost_putc(int c)
{
	svc(kSYS_WRITEC, &c);
}

/*
 * QEMU does not support returning a proper exit code.  You
 * can just call it with the magic constant 0x20026 to indicate
 * a successful exit or anything else to indicate a failure.
 */
void qemu_semihost_exit(int retcode)
{
	if (retcode == 0)
		svc(kSYS_EXIT, (void*)0x20026);
	else
		svc(kSYS_EXIT, (void*)retcode);
}
