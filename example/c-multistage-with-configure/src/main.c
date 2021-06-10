#include <stdio.h>
#include "Generated/Configuration.h"

int main() {
    static const char *const message =
        #if CONFIGURATION_HAS_MONOTONIC_CLOCK
            "have a monotonic clock!";
        #else
            "what a pitty: have no monotonic clock";
        #endif

    printf("%s\n", message);
    return 0;
}
