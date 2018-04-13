//name: test_utilities
//type: qemu_semihost_unit
//module: utilities.c

#include "utilities.h"
#include "unity.h"

void test_utilities()
{
	int result = add(1, 2);

	TEST_ASSERT(result == 3)
}
