#include <stdint.h>
extern int64_t silica_entry(void) __asm__("main");
int64_t call_silica(void) { return silica_entry(); }
