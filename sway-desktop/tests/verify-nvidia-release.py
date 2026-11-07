#!/usr/bin/env python3
"""Exercise the patched DRM retirement functions with real wlroots buffers/swapchain.

Only DRM timeline IO and mgpu teardown are stubbed: this requires no display/GPU.
Usage: verify-nvidia-release.py WLROOTS_SOURCE WLROOTS_BUILD
"""
import os, pathlib, shlex, subprocess, sys, tempfile

src, build = map(lambda s: pathlib.Path(s).resolve(), sys.argv[1:3])

def function(path, signature):
    text = (src / path).read_text()
    start = text.index(signature)
    brace = text.index('{', start)
    level = 1
    end = brace + 1
    while level:
        level += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'

functions = ''.join(function('backend/drm/fb.c', sig) for sig in (
    'void drm_fb_clear(', 'struct wlr_drm_fb *drm_fb_lock(',
    'void drm_fb_move(', 'void drm_fb_copy('))
functions += ''.join(function('backend/drm/drm.c', sig) for sig in (
    'static void drm_plane_release_previous(',
    'static void drm_plane_finish_page_flip(',
    'static void drm_plane_finish_surface('))

code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <drm_fourcc.h>
#include <wlr/interfaces/wlr_buffer.h>
#include <wlr/render/allocator.h>
#include <wlr/render/drm_syncobj.h>
#include <wlr/render/swapchain.h>
#include <wlr/types/wlr_buffer.h>
#include "backend/drm/drm.h"
#include "backend/drm/fb.h"

// Keep extracted test symbols separate from the archive's internal symbols.
#define drm_fb_clear test_drm_fb_clear
#define drm_fb_lock test_drm_fb_lock
#define drm_fb_move test_drm_fb_move
#define drm_fb_copy test_drm_fb_copy
#define wlr_drm_syncobj_timeline_signal test_timeline_signal
#define wlr_drm_syncobj_timeline_unref test_timeline_unref
#define finish_drm_surface test_finish_drm_surface

static unsigned allocated, destroyed;
struct test_buffer { struct wlr_buffer base; struct wlr_drm_fb fb; };
struct test_timeline { unsigned refs, calls; uint64_t point; };
bool wlr_drm_syncobj_timeline_signal(struct wlr_drm_syncobj_timeline *timeline, uint64_t point) {
    struct test_timeline *t = (void *)timeline;
    assert(t->refs > 0);
    if (point > t->point) t->point = point;
    t->calls++;
    return true;
}
void wlr_drm_syncobj_timeline_unref(struct wlr_drm_syncobj_timeline *timeline) {
    if (timeline) {
        struct test_timeline *t = (void *)timeline;
        assert(t->refs > 0);
        t->refs--;
    }
}
void finish_drm_surface(struct wlr_drm_surface *surface) { (void)surface; }
static void destroy_buffer(struct wlr_buffer *buf) { destroyed++; free(buf); }
static const struct wlr_buffer_impl buffer_impl = { .destroy = destroy_buffer };
static struct wlr_buffer *create_buffer(struct wlr_allocator *alloc, int width,
        int height, const struct wlr_drm_format *format) {
    (void)alloc; (void)format;
    struct test_buffer *buf = calloc(1, sizeof(*buf));
    assert(buf);
    wlr_buffer_init(&buf->base, &buffer_impl, width, height);
    buf->fb.wlr_buf = &buf->base;
    allocated++;
    return &buf->base;
}
static void destroy_allocator(struct wlr_allocator *alloc) { (void)alloc; }
static const struct wlr_allocator_interface allocator_impl = {
    .create_buffer = create_buffer, .destroy = destroy_allocator,
};
'''
code += functions
code += r'''
static void queue(struct wlr_drm_plane *p, struct wlr_buffer *buf,
        struct test_timeline *t, uint64_t point) {
    assert(p->queued_fb == NULL);
    struct test_buffer *b = (void *)buf;
    drm_fb_copy(&p->queued_fb, &b->fb);
    if (t) {
        p->queued_release_timeline = (void *)t;
        p->queued_release_point = point;
        t->refs++;
    }
    wlr_buffer_unlock(buf);
}
static struct wlr_swapchain *new_swapchain(struct wlr_allocator *alloc) {
    const struct wlr_drm_format format = { .format = DRM_FORMAT_XRGB2101010 };
    struct wlr_swapchain *chain = wlr_swapchain_create(alloc, 3440, 1440, &format);
    assert(chain);
    return chain;
}
static void rotation(struct wlr_allocator *alloc, bool delayed, bool sync) {
    struct wlr_swapchain *chain = new_swapchain(alloc);
    struct wlr_drm_plane p = {0};
    struct test_timeline t = {0};
    struct test_timeline *timeline = sync ? &t : NULL;
    unsigned before = allocated;
    struct wlr_buffer *a = wlr_swapchain_acquire(chain);
    queue(&p, a, timeline, 1);
    drm_plane_finish_page_flip(&p, delayed);
    struct wlr_buffer *b = wlr_swapchain_acquire(chain);
    assert(b != a);
    queue(&p, b, timeline, 2);
    drm_plane_finish_page_flip(&p, delayed);
    assert(a->n_locks == (delayed ? 1 : 0));
    if (sync) assert(t.point == (delayed ? 0 : 1));
    struct wlr_buffer *c = wlr_swapchain_acquire(chain);
    assert((c != a) == delayed); // baseline must actually reproduce immediate reuse
    assert(c != b);
    queue(&p, c, timeline, 3);
    drm_plane_finish_page_flip(&p, delayed);
    if (sync) assert(t.point == (delayed ? 1 : 2));
    assert(allocated - before == (delayed ? 3 : 2));

    // 1000 flips: bounded triple rotation; no buffer exhaustion, no premature reuse.
    for (uint64_t i = 4; i < 1004; i++) {
        struct wlr_buffer *next = wlr_swapchain_acquire(chain);
        assert(next != p.current_fb->wlr_buf);
        if (p.previous_fb) assert(next != p.previous_fb->wlr_buf);
        queue(&p, next, timeline, i);
        drm_plane_finish_page_flip(&p, delayed);
        if (sync) assert(t.point == i - (delayed ? 2 : 1));
    }
    assert(allocated - before == (delayed ? 3 : 2));

    // A failed/test-only commit never enters apply_commit/finish_page_flip.
    // Even an unrelated flip with no queued FB must not retire the held buffer.
    struct wlr_drm_fb *previous = p.previous_fb;
    uint64_t signaled = t.point;
    drm_plane_finish_page_flip(&p, delayed);
    assert(p.previous_fb == previous && t.point == signaled);

    // Pending frame plus DPMS disable/destruction: release every held lock/timeline once.
    queue(&p, wlr_swapchain_acquire(chain), timeline, 1004);
    drm_plane_finish_surface(&p);
    assert(!p.previous_fb && !p.current_fb && !p.queued_fb);
    if (sync) assert(t.refs == 0 && t.point == 1004 && t.calls == 1004);
    drm_plane_finish_surface(&p); // idempotent
    wlr_swapchain_destroy(chain);
}
static void same_fb_and_independent_outputs(struct wlr_allocator *alloc) {
    struct wlr_swapchain *chain = new_swapchain(alloc);
    struct wlr_drm_plane p = {0}, other = {0};
    struct test_timeline t = {0};
    struct wlr_buffer *a = wlr_swapchain_acquire(chain);
    queue(&p, a, &t, 1);
    drm_plane_finish_page_flip(&p, true);
    queue(&p, wlr_buffer_lock(a), &t, 2); // property-only recommit of current FB
    drm_plane_finish_page_flip(&p, true);
    assert(a->n_locks == 2 && t.point == 0);
    queue(&p, wlr_buffer_lock(a), &t, 3);
    drm_plane_finish_page_flip(&p, true);
    assert(a->n_locks == 2 && t.point == 1);
    // Other CRTC events cannot age this plane's preceding frame.
    drm_plane_finish_page_flip(&other, true);
    assert(a->n_locks == 2 && t.point == 1);
    drm_plane_finish_surface(&p);
    assert(a->n_locks == 0 && t.refs == 0 && t.point == 3 && t.calls == 3);
    wlr_swapchain_destroy(chain);
}
int main(void) {
    struct wlr_allocator alloc;
    wlr_allocator_init(&alloc, &allocator_impl, 0);
    rotation(&alloc, false, false);
    rotation(&alloc, false, true);
    rotation(&alloc, true, false);
    rotation(&alloc, true, true);
    same_fb_and_independent_outputs(&alloc);
    assert(allocated == destroyed);
    printf("PASS: real wlroots swapchain/buffer, baseline immediate reuse, guarded triple rotation, explicit/implicit sync, 4000 flips, repeated FB, independent CRTC, idle, teardown (%u buffers)\n", allocated);
}
'''
with tempfile.TemporaryDirectory(prefix='nvidia-release-') as tmp:
    tmp = pathlib.Path(tmp)
    (tmp / 'test.c').write_text(code)
    # Reuse verify-hdr-pixels.py's standalone/subproject, static/shared lookup.
    library = next(p for p in (build/'libwlroots-0.20.a', build/'libwlroots-0.20.so') if p.is_file())
    env = os.environ.copy()
    for root in [build, *build.parents]:
        pcdir = root/'meson-uninstalled'
        if (pcdir/'wlroots-0.20-uninstalled.pc').is_file():
            env['PKG_CONFIG_PATH'] = str(pcdir) + os.pathsep + env.get('PKG_CONFIG_PATH', '')
            break
    else:
        raise SystemExit('Missing generated wlroots pkg-config metadata')
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs',
        '--static', 'wlroots-0.20'], env=env, text=True))
    flags = [str(library) if f == '-lwlroots-0.20' else f for f in flags]
    cmd = ['cc', '-g', '-Wall', '-Wextra', '-Werror', '-DWLR_USE_UNSTABLE', '-DWLR_PRIVATE=',
        '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
        '-I'+str(src/'include'), '-I'+str(build/'include'),
        str(tmp/'test.c'), '-Wl,-rpath,'+str(build),
        '-o', str(tmp/'test'), *flags]
    subprocess.run(cmd, check=True)
    subprocess.run([str(tmp/'test')], check=True)
