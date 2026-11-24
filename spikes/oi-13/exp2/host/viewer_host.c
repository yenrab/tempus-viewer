#include "viewer_host.h"
#include <pthread.h>
#include <stdlib.h>
#include <string.h>

extern int64_t silica_entry(void) __asm__("main");

typedef struct node { uint8_t *p; uint64_t n; struct node *next; } node;
static node *head, *tail;
static pthread_mutex_t mu = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t cv = PTHREAD_COND_INITIALIZER;
static void (*handler)(const uint8_t *, uint64_t);

void viewer_host_set_handler(void (*h)(const uint8_t *, uint64_t)) { handler = h; }

void viewer_host_push_event(const uint8_t *p, uint64_t n) {
    node *e = malloc(sizeof *e);
    e->p = malloc(n ? n : 1); memcpy(e->p, p, n); e->n = n; e->next = 0;
    pthread_mutex_lock(&mu);
    if (tail) tail->next = e; else head = e;
    tail = e;
    pthread_cond_signal(&cv);
    pthread_mutex_unlock(&mu);
}

viewer_host_result viewer_next_event(void) {
    viewer_host_result r = {0, 0, 0, 0};
    pthread_mutex_lock(&mu);
    while (!head) pthread_cond_wait(&cv, &mu);
    node *e = head; head = e->next; if (!head) tail = 0;
    pthread_mutex_unlock(&mu);
    r.text_ptr = e->p; r.text_len = e->n;   /* buffer is leaked in the spike */
    free(e);
    return r;
}

viewer_host_result viewer_post(const uint8_t *p, uint64_t n) {
    viewer_host_result r = {0, 0, 0, 0};
    if (handler) handler(p, n);
    else r.tag = 1, r.error_code = 1;
    return r;
}

int64_t viewer_host_start_silica(void) { return silica_entry(); }
