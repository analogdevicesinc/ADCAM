/*
 * MIT License
 *
 * Copyright (c) 2026 Analog Devices, Inc.
 *
 * Zeroing allocator shim (LD_PRELOAD).
 *
 * Workaround for a confirmed bug in the closed-source libtofi_compute.so:
 * FreeComputeDepth() (reached via FreeTofiCompute) frees an internal pointer
 * that InitTofiCompute() left UNINITIALIZED. On a normal heap that pointer is
 * sometimes 0 (fresh pages -> free(NULL) is a no-op) and sometimes garbage
 * (dirty chunk -> "double free or corruption" crash). This was confirmed with
 * AddressSanitizer: free() of 0xbebebe... (ASan's uninitialized-memory fill)
 * inside FreeComputeDepth on every mode switch / stop->start in the viewer.
 *
 * By zero-filling every allocation, any such uninitialized pointer reads as
 * NULL, so the library's free() becomes a safe no-op. This is a client-side
 * mitigation; the proper fix is for ADI to initialize the pointer in
 * libtofi_compute.so.
 *
 * Build:
 *   gcc -shared -fPIC -O2 -o libzeroalloc.so zeroalloc.c -ldl
 * Use:
 *   LD_PRELOAD=/path/to/libzeroalloc.so ./ADIToFGUI
 */

#define _GNU_SOURCE
#include <dlfcn.h>
#include <stddef.h>
#include <string.h>

static void *(*real_malloc)(size_t) = NULL;
static void *(*real_realloc)(void *, size_t) = NULL;
static void *(*real_memalign)(size_t, size_t) = NULL;
static int (*real_posix_memalign)(void **, size_t, size_t) = NULL;
static void (*real_free)(void *) = NULL;

/* Minimal bump allocator used only while dlsym() is resolving the real
 * symbols (dlsym may itself call calloc). A few KB is plenty. */
static char g_bootstrap[8192];
static size_t g_bootstrap_off = 0;

static void *bootstrap_alloc(size_t size) {
    size_t aligned = (size + 15u) & ~((size_t)15u);
    if (g_bootstrap_off + aligned > sizeof(g_bootstrap)) {
        return NULL;
    }
    void *p = &g_bootstrap[g_bootstrap_off];
    g_bootstrap_off += aligned;
    return p; /* already zero: static storage */
}

static int is_bootstrap_ptr(void *p) {
    return (char *)p >= g_bootstrap &&
           (char *)p < g_bootstrap + sizeof(g_bootstrap);
}

static void init_real(void) {
    if (!real_malloc) {
        real_malloc = (void *(*)(size_t))dlsym(RTLD_NEXT, "malloc");
        real_realloc = (void *(*)(void *, size_t))dlsym(RTLD_NEXT, "realloc");
        real_memalign = (void *(*)(size_t, size_t))dlsym(RTLD_NEXT, "memalign");
        real_posix_memalign =
            (int (*)(void **, size_t, size_t))dlsym(RTLD_NEXT, "posix_memalign");
        real_free = (void (*)(void *))dlsym(RTLD_NEXT, "free");
    }
}

void free(void *ptr) {
    if (!ptr) {
        return;
    }
    if (is_bootstrap_ptr(ptr)) {
        return; /* bootstrap memory is static; never freed */
    }
    if (!real_free) {
        init_real();
    }
    if (real_free) {
        real_free(ptr);
    }
}

void *malloc(size_t size) {
    if (!real_malloc) {
        init_real();
        if (!real_malloc) {
            return bootstrap_alloc(size);
        }
    }
    void *p = real_malloc(size);
    if (p) {
        memset(p, 0, size);
    }
    return p;
}

void *calloc(size_t nmemb, size_t size) {
    /* calloc already returns zeroed memory; just route through malloc. */
    size_t total = nmemb * size;
    if (size != 0 && total / size != nmemb) {
        return NULL; /* overflow */
    }
    return malloc(total);
}

void *realloc(void *ptr, size_t size) {
    if (!real_realloc) {
        init_real();
    }
    if (is_bootstrap_ptr(ptr)) {
        void *p = malloc(size);
        return p;
    }
    /* Note: newly grown bytes are not zeroed here; the library's uninitialized
     * pointers come from fresh malloc/calloc, which we cover above. */
    return real_realloc ? real_realloc(ptr, size) : NULL;
}

void *memalign(size_t alignment, size_t size) {
    if (!real_memalign) {
        init_real();
    }
    void *p = real_memalign ? real_memalign(alignment, size) : NULL;
    if (p) {
        memset(p, 0, size);
    }
    return p;
}

void *aligned_alloc(size_t alignment, size_t size) {
    return memalign(alignment, size);
}

int posix_memalign(void **memptr, size_t alignment, size_t size) {
    if (!real_posix_memalign) {
        init_real();
    }
    if (!real_posix_memalign) {
        return 1;
    }
    int rc = real_posix_memalign(memptr, alignment, size);
    if (rc == 0 && *memptr) {
        memset(*memptr, 0, size);
    }
    return rc;
}
