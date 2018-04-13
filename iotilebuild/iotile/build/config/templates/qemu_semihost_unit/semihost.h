#ifndef __semihost_h__
#define __semihost_h__

//Supported QEMU service calls
#define kSYS_WRITEC		0x03
#define KSYS_WRITE0		0x04
#define kSYS_EXIT		0x18

//Internal API, calling it externally should not be needed (the below functions wrap it)
void __attribute__((noinline)) svc(volatile unsigned int arg0, volatile void *arg1);

//Semihosting service calls
void qemu_semihost_putc(int c);
void qemu_semihost_exit(int retcode);

#endif
