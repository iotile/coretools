\#include "unity.h"

//Test function prototypes

int main(void)
{
	int retval;

	UNITY_BEGIN();

	//Test function calls

	retval = UNITY_END();
	qemu_semihost_exit(retval);
}
