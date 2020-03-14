/**
 * @file
 * The one and only.
 */

#include <stdio.h>
#include "Generated/Version.h"

/**
 * Show the application's version.
 *
 * @return 0
 */
int main() {
    printf("version: " APPLICATION_VERSION "\n");
    return 0;
}
