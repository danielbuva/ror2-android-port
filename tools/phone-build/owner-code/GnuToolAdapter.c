/* Authored GNU host-tool adapters for the explicit Android x86_64/QEMU runner. */
#define _GNU_SOURCE
#include <stddef.h>
#include <stdint.h>

/* Supports both EM_X86_64 (62) and EM_AARCH64 (183) ELF binaries */
int ror2_check_elf_machine(const unsigned char *h) {
    if (h[0] != 127 || h[1] != 'E' || h[2] != 'L' || h[3] != 'F') return 0;
    if (h[18] == 62 || h[18] == 183) return 1;
    return 0;
}
