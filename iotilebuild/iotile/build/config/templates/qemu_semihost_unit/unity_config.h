#ifndef __UNITY_CONFIG_H__
#define __UNITY_CONFIG_H__

#include "semihost.h"

#define UNITY_OUTPUT_CHAR(a)	qemu_semihost_putc(a)
  
#define UNITY_EXCLUDE_FLOAT

#endif
