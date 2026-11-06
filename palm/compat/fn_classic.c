/* Classic fujinet-lib network calls (fujinet-network.h) on fujinet-nio-lib,
 * so fujinet-palm apps run over the Springboard unchanged.
 *
 * network_open() opens an NIO HTTP session; network_read() reads it in
 * order. Shared-library JSON queries retain that handle and use NIO's
 * TranslateConfigure to select fields from its cached response, without GETs.
 * The legacy static build remains unchanged. */
#include <stdbool.h> /* must precede PalmOS.h on prc-tools */
#ifdef NIO_SHARED_CLIENT
#include "NioLibClient.h"
#else
#include "fujinet-nio.h"
#endif
#include "fujinet-network.h"
#include "fujinet-palmos.h"
#include <string.h>
#include <PalmOS.h>   /* after stdbool.h, see fnapp.h */

#define SLOTS 4
#define URL_MAX 256
#define READ_CHUNK 512
#define NOT_READY_TRIES 400   /* x 50 ms */

typedef struct {
    char spec[URL_MAX + 4];
    fn_handle_t handle;
    uint8_t open, json, eof;
    uint32_t offset;
} slot_t;

static slot_t slots[SLOTS];
static uint8_t initialized;
static uint16_t last_error;

/* Shared clients end their owner on a failed operation as well as app exit.
 * Keep the old static transport's lifecycle behavior unchanged. */
static void failed(uint16_t error)
{
    last_error = error;
#ifdef NIO_SHARED_CLIENT
    fuji_palmos_close();
#endif
}

#define WAIT() SysTaskDelay(5)   /* ticks: 50 ms on a Visor */

static const char *url_of(const char *spec)
{
    if (spec[0] == 'N' && spec[1] == ':') return spec + 2;
    if (spec[0] == 'N' && spec[1] >= '0' && spec[1] <= '9' && spec[2] == ':') return spec + 3;
    return spec;
}

static uint8_t ready(void)
{
    uint8_t err;
    if (initialized) return 1;
    err = fn_init();
    if (err) {
        last_error = err;
#ifdef NIO_SHARED_CLIENT
        FrmCustomAlert(9000, "NioLib unavailable", "Install NioLib ABI 1.1; check module/host.", "");
#endif
        return 0;
    }
    initialized = 1;
    return 1;
}

static slot_t *find(const char *spec)
{
    uint8_t i;
    for (i = 0; i < SLOTS; i++)
        if (slots[i].spec[0] && !strcmp(slots[i].spec, spec)) return &slots[i];
    return 0;
}

static slot_t *claim(const char *spec)
{
    uint8_t i;
    for (i = 0; i < SLOTS; i++) {
        if (!slots[i].spec[0]) {
            memset(&slots[i], 0, sizeof slots[i]);
            strncpy(slots[i].spec, spec, sizeof slots[i].spec - 1);
            return &slots[i];
        }
    }
    return 0;
}

static void release(slot_t *s)
{
    if (s->open) fn_close(s->handle);
    s->open = 0;
    s->spec[0] = 0;
}

FN_ERR network_open(const char *devicespec, uint8_t mode, uint8_t trans)
{
    slot_t *s;
    uint8_t err, iflags = 0;
    uint16_t status = 0, tries;
    uint32_t length = 0;

    (void)mode;
    (void)trans;
    if (!ready()) return FN_ERR_OFFLINE;
    if (strlen(url_of(devicespec)) >= URL_MAX) {
        failed(FN_ERR_URL_TOO_LONG);
        return FN_ERR_BAD_CMD;
    }
    s = find(devicespec);
    if (s) release(s);
    s = claim(devicespec);
    if (!s) {
        failed(FN_ERR_NO_HANDLES);
        return FN_ERR_IO_ERROR;
    }
    err = fn_open(&s->handle, FN_METHOD_GET, url_of(devicespec), FN_OPEN_FOLLOW_REDIR);
    if (err) {
        s->spec[0] = 0;
        failed(err);
        return FN_ERR_IO_ERROR;
    }
    s->open = 1;
    for (tries = 0; tries < NOT_READY_TRIES; tries++) {
        err = fn_info(s->handle, &status, &length, &iflags);
        if (err != FN_ERR_NOT_READY) break;
        WAIT();
    }
    if (status >= 400) {
        release(s);
        failed(status);
        return FN_ERR_IO_ERROR;
    }
    if (err) {
        release(s);
        failed(err);
        return FN_ERR_IO_ERROR;
    }
    return FN_ERR_OK;
}

int16_t network_read(const char *devicespec, void *buf, uint16_t len)
{
    slot_t *s = find(devicespec);
    uint16_t total = 0, got, want, tries = 0;
    uint8_t err, flags;

    if (!s || !s->open) return -(int16_t)FN_ERR_BAD_CMD;
    while (total < len && !s->eof) {
        want = len - total;
        if (want > READ_CHUNK) want = READ_CHUNK;
        got = 0;
        flags = 0;
        err = fn_read(s->handle, s->offset, (uint8_t *)buf + total, want, &got, &flags);
        if (err == FN_ERR_NOT_READY) {
            if (++tries > NOT_READY_TRIES) break;
            WAIT();
            continue;
        }
        if (err) {
            failed(err);
            return total ? (int16_t)total : -(int16_t)FN_ERR_IO_ERROR;
        }
        tries = 0;
        s->offset += got;
        total += got;
        if (flags & FN_READ_EOF) s->eof = 1;
        else if (!got) break;
    }
    return (int16_t)total;
}

FN_ERR network_json_parse(const char *devicespec)
{
    slot_t *s = find(devicespec);
    if (!s) return FN_ERR_BAD_CMD;
#ifndef NIO_SHARED_CLIENT
    if (s->open) fn_close(s->handle);
    s->open = 0;
#else
    if (!s->open) return FN_ERR_BAD_CMD;
#endif
    s->json = 1;
    return FN_ERR_OK;
}

int16_t network_json_query_n(const char *devicespec, const char *query, char *buffer, uint16_t buflen)
{
    slot_t *s = find(devicespec);
    fn_handle_t h;
    uint8_t err, flags = 0, chunk[64];
    uint16_t got, n = 0, tries = 0;
    uint32_t offset = 0;

    if (!buflen) return 0;
    buffer[0] = 0;
    if (!s || !s->json) return -(int16_t)FN_ERR_BAD_CMD;
#ifdef NIO_SHARED_CLIENT
    if (!s->open) return -(int16_t)FN_ERR_BAD_CMD;
    h = s->handle;
    err = fn_json_query(h, query);
    /* NotReady may follow successful selector application while the first
     * body is still downloading. Poll Read, never repeat configuration and
     * discard a partially cached body. Later fields reuse this same handle. */
    if (err == FN_ERR_UNSUPPORTED)
        FrmCustomAlert(9000, "JSON support unavailable", "Install NioLib ABI 1.4 for these apps.", "");
    if (err && err != FN_ERR_NOT_READY) {
#else
    err = fn_open_translated(&h, FN_METHOD_GET, url_of(devicespec), FN_OPEN_FOLLOW_REDIR,
                             FN_TRANSLATE_JSON, 0, query);
    if (err) {
#endif
        failed(err);
        return -(int16_t)FN_ERR_IO_ERROR;
    }
    for (;;) {
        got = 0;
        flags = 0;
        err = fn_read(h, offset, chunk, sizeof chunk, &got, &flags);
        if (err == FN_ERR_NOT_READY) {
            if (++tries > NOT_READY_TRIES) break;
            WAIT();
            continue;
        }
        if (err) {
            last_error = err;
            break;
        }
        offset += got;
        /* Keep what fits; read the rest so the session ends cleanly. */
        if (n < buflen - 1) {
            uint16_t keep = got < buflen - 1 - n ? got : buflen - 1 - n;
            memcpy(buffer + n, chunk, keep);
            n += keep;
        }
        if ((flags & FN_READ_EOF) || !got) break;
    }
#ifndef NIO_SHARED_CLIENT
    fn_close(h);
#endif
    if (err) failed(err);
    buffer[n] = 0;
    return err ? -(int16_t)FN_ERR_IO_ERROR : (int16_t)n;
}

int16_t network_json_query(const char *devicespec, const char *query, char *buffer)
{
    return network_json_query_n(devicespec, query, buffer, 128);
}

FN_ERR network_status(const char *devicespec, uint16_t *bw, uint8_t *c, uint8_t *err)
{
    slot_t *s = find(devicespec);
    if (bw) *bw = 0;
    if (c) *c = s && s->open && !s->eof ? 1 : 0;
    if (err) *err = 0;
    return s ? FN_ERR_OK : FN_ERR_BAD_CMD;
}

FN_ERR network_close(const char *devicespec)
{
    slot_t *s = find(devicespec);
    if (s) release(s);
    return FN_ERR_OK;
}

void fuji_palmos_close(void)
{
    uint8_t i;
    for (i = 0; i < SLOTS; i++)
        if (slots[i].spec[0]) release(&slots[i]);
    if (initialized) fn_shutdown();
    initialized = 0;
    memset(slots, 0, sizeof slots);
}

bool fuji_palmos_is_open(void) { return initialized != 0; }

uint16_t fuji_palmos_last_error(void) { return last_error; }
