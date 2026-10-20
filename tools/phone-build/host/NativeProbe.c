#include <stdio.h>
#include <unistd.h>

int main(void)
{
    char context[256] = "unavailable";
    FILE *attribute = fopen("/proc/self/attr/current", "r");
    if (attribute != NULL) {
        if (fgets(context, sizeof(context), attribute) == NULL)
            snprintf(context, sizeof(context), "unavailable");
        fclose(attribute);
    }
    for (char *p = context; *p; ++p) {
        if (*p == '\n') { *p = 0; break; }
        if (*p < 32 || *p == '"' || *p == '\\') *p = '_';
    }
    printf("{\"marker\":\"authored-phone-host-v1\",\"answer\":42,\"uid\":%u,\"context\":\"%s\"}\n",
           (unsigned)getuid(), context);
    return 0;
}
