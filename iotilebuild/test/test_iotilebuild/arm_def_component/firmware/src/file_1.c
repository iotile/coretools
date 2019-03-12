#ifdef kTestDefine
#error kTestDefine is defined but should have been undefined by a subsequent architecture
#endif

int main(void)
{
    return 1;
}

void Reset_Handler()
{
    
}