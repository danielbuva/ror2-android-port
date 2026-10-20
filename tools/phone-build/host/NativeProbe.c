#include <stdio.h>
#include <unistd.h>

int main(void)
{
    printf("{\"marker\":\"authored-phone-host-v1\",\"answer\":42,\"uid\":%u}\n",
           (unsigned)getuid());
    return 0;
}
