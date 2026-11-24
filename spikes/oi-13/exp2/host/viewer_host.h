#ifndef VIEWER_HOST_H
#define VIEWER_HOST_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

typedef struct viewer_host_result {
    int64_t tag;
    const uint8_t *text_ptr;
    uint64_t text_len;
    int64_t error_code;
} viewer_host_result;

/* Called by Silica's FFI workers (not by Swift). */
viewer_host_result viewer_next_event(void);                       /* blocks until Swift pushes an event */
viewer_host_result viewer_post(const uint8_t *text_ptr, uint64_t text_len); /* calls Swift's handler on the caller's thread */

/* Called by Swift. */
void viewer_host_push_event(const uint8_t *text_ptr, uint64_t text_len);
void viewer_host_set_handler(void (*handler)(const uint8_t *, uint64_t));
int64_t viewer_host_start_silica(void);                           /* runs the Silica main; blocks */

#ifdef __cplusplus
}
#endif
#endif
