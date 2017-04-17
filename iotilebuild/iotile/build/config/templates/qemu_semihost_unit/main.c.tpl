\#include "unity.h"
\#include "semihost.h"

//Test Function Prototypes
#for $test_func in $tests
void ${test_func}(void);
#end for

int main(void)
{
    UNITY_BEGIN();
#for $test_func in $tests
    RUN_TEST($test_func);
#end for
    qemu_semihost_exit(UNITY_END());

    //We never get here because qemu exits from the above semihost call
    return 0;
}
