#define _GNU_SOURCE
/* Exercise the actual color-management wire protocol, including NVIDIA/Wine's
 * version-1 binding. Runs only against verify-hdr.py's isolated compositor. */
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <wayland-client.h>
#include "color-management-v1-client-protocol.h"

static struct wp_color_manager_v1 *manager;
static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct wl_output *output;
static int output_changes, preferred_changes;
static bool windows_scrgb, ready;
static uint32_t bind_version;
static void supported_intent(void *data, struct wp_color_manager_v1 *obj, uint32_t value) {}
static void supported_feature(void *data, struct wp_color_manager_v1 *obj, uint32_t value) {
    if (value == WP_COLOR_MANAGER_V1_FEATURE_WINDOWS_SCRGB) windows_scrgb = true;
}
static void supported_tf(void *data, struct wp_color_manager_v1 *obj, uint32_t value) {}
static void supported_primaries(void *data, struct wp_color_manager_v1 *obj, uint32_t value) {}
static void manager_done(void *data, struct wp_color_manager_v1 *obj) {}
static const struct wp_color_manager_v1_listener manager_listener = {
    .supported_intent = supported_intent, .supported_feature = supported_feature,
    .supported_tf_named = supported_tf, .supported_primaries_named = supported_primaries,
    .done = manager_done,
};
static void global(void *data, struct wl_registry *registry, uint32_t name,
        const char *interface, uint32_t version) {
    if (!strcmp(interface, "wp_color_manager_v1")) {
        assert(version >= bind_version);
        manager = wl_registry_bind(registry, name, &wp_color_manager_v1_interface, bind_version);
        wp_color_manager_v1_add_listener(manager, &manager_listener, NULL);
    } else if (!strcmp(interface, "wl_shm")) {
        shm = wl_registry_bind(registry, name, &wl_shm_interface, 1);
    } else if (!strcmp(interface, "wl_output")) {
        if (!output) output = wl_registry_bind(registry, name, &wl_output_interface, 1);
    } else if (!strcmp(interface, "wl_compositor")) {
        compositor = wl_registry_bind(registry, name, &wl_compositor_interface, 1);
    }
}
static void global_remove(void *data, struct wl_registry *registry, uint32_t name) {}
static const struct wl_registry_listener registry_listener = {global, global_remove};
static void description_failed(void *data, struct wp_image_description_v1 *obj,
        uint32_t cause, const char *message) {
    fprintf(stderr, "Windows-scRGB failed: %u: %s\n", cause, message);
    assert(false);
}
static void description_ready(void *data, struct wp_image_description_v1 *obj, uint32_t identity) {
    assert(bind_version == 1 && identity);
    ready = true;
}
static void description_ready2(void *data, struct wp_image_description_v1 *obj,
        uint32_t identity_hi, uint32_t identity_lo) {
    assert(bind_version == 2 && (identity_hi || identity_lo));
    ready = true;
}
static const struct wp_image_description_v1_listener description_listener = {
    .failed = description_failed, .ready = description_ready, .ready2 = description_ready2,
};
static void exercise(uint32_t version, bool forbidden_information) {
    bind_version = version;
    manager = NULL; compositor = NULL; windows_scrgb = ready = false;
    struct wl_display *display = wl_display_connect(NULL);
    assert(display);
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);
    assert(wl_display_roundtrip(display) >= 0);
    assert(wl_display_roundtrip(display) >= 0);
    assert(manager && compositor && windows_scrgb);
    struct wp_image_description_v1 *desc = wp_color_manager_v1_create_windows_scrgb(manager);
    wp_image_description_v1_add_listener(desc, &description_listener, NULL);
    assert(wl_display_roundtrip(display) >= 0 && ready);
    if (forbidden_information) {
        struct wp_image_description_info_v1 *info = wp_image_description_v1_get_information(desc);
        assert(wl_display_roundtrip(display) < 0);
        assert(wl_display_get_error(display) == EPROTO);
        const struct wl_interface *interface;
        uint32_t object_id;
        assert(wl_display_get_protocol_error(display, &interface, &object_id) ==
            WP_IMAGE_DESCRIPTION_V1_ERROR_NO_INFORMATION);
        assert(interface == &wp_image_description_v1_interface);
        wp_image_description_info_v1_destroy(info);
    } else {
        struct wl_surface *surface = wl_compositor_create_surface(compositor);
        struct wp_color_management_surface_v1 *color = wp_color_manager_v1_get_surface(manager, surface);
        wp_color_management_surface_v1_set_image_description(color, desc,
            WP_COLOR_MANAGER_V1_RENDER_INTENT_PERCEPTUAL);
        wl_surface_commit(surface);
        /* The committed description must survive destruction of its protocol object. */
        wp_image_description_v1_destroy(desc);
        desc = NULL;
        assert(wl_display_roundtrip(display) >= 0);
        wp_color_management_surface_v1_unset_image_description(color);
        wl_surface_commit(surface);
        assert(wl_display_roundtrip(display) >= 0);
        wp_color_management_surface_v1_destroy(color);
        wl_surface_destroy(surface);
    }
    if (desc) wp_image_description_v1_destroy(desc);
    wp_color_manager_v1_destroy(manager);
    wl_compositor_destroy(compositor);
    wl_registry_destroy(registry);
    wl_display_disconnect(display);
    printf("PASS: Windows-scRGB protocol v%u %s\n", version,
        forbidden_information ? "get_information correctly forbidden" : "feature, ready, surface set/unset");
}
struct snapshot {
    uint32_t min, max, reference, target_min, target_max;
    int32_t target_red_x;
    bool done;
};
static void info_done(void *data, struct wp_image_description_info_v1 *info) {
    ((struct snapshot *)data)->done=true;
}
static void info_icc(void *data, struct wp_image_description_info_v1 *info, int32_t fd, uint32_t size) {
    close(fd); assert(false);
}
static void info_primaries(void *data, struct wp_image_description_info_v1 *info,
    int32_t rx,int32_t ry,int32_t gx,int32_t gy,int32_t bx,int32_t by,int32_t wx,int32_t wy) {}
static void info_named(void *data, struct wp_image_description_info_v1 *info, uint32_t value) {}
static void info_luminances(void *data, struct wp_image_description_info_v1 *info,
    uint32_t min,uint32_t max,uint32_t reference) {
    struct snapshot *s=data;s->min=min;s->max=max;s->reference=reference;
}
static void info_target_primaries(void *data, struct wp_image_description_info_v1 *info,
    int32_t rx,int32_t ry,int32_t gx,int32_t gy,int32_t bx,int32_t by,int32_t wx,int32_t wy) {
    ((struct snapshot *)data)->target_red_x=rx;
}
static void info_target_luminance(void *data, struct wp_image_description_info_v1 *info,
    uint32_t min,uint32_t max) {
    struct snapshot *s=data;s->target_min=min;s->target_max=max;
}
static const struct wp_image_description_info_v1_listener info_listener={
    .done=info_done,.icc_file=info_icc,.primaries=info_primaries,.primaries_named=info_named,
    .tf_power=info_named,.tf_named=info_named,.luminances=info_luminances,
    .target_primaries=info_target_primaries,.target_luminance=info_target_luminance,
    .target_max_cll=info_named,.target_max_fall=info_named,
};
static void inspect(struct wl_display *display, struct wp_image_description_v1 *desc,
        uint32_t peak, uint32_t reference) {
    struct snapshot snapshot={0};
    struct wp_image_description_info_v1 *info=wp_image_description_v1_get_information(desc);
    wp_image_description_info_v1_add_listener(info,&info_listener,&snapshot);
    assert(wl_display_roundtrip(display)>=0 && snapshot.done);
    assert(snapshot.max==10000 && snapshot.reference==reference);
    assert(snapshot.target_min==50 && snapshot.target_max==peak);
    assert(snapshot.target_red_x==640000);
    wp_image_description_info_v1_destroy(info);
}
static void output_changed(void *data, struct wp_color_management_output_v1 *color) {output_changes++;}
static const struct wp_color_management_output_v1_listener output_listener={.image_description_changed=output_changed};
static void preferred_changed(void *data, struct wp_color_management_surface_feedback_v1 *feedback, uint32_t id) {preferred_changes++;}
static void preferred_changed2(void *data, struct wp_color_management_surface_feedback_v1 *feedback,
        uint32_t hi,uint32_t lo) {preferred_changes++;}
static const struct wp_color_management_surface_feedback_v1_listener feedback_listener={
    .preferred_changed=preferred_changed,.preferred_changed2=preferred_changed2,
};
static void wait_ready(struct wl_display *display, struct wp_image_description_v1 *desc) {
    ready=false;wp_image_description_v1_add_listener(desc,&description_listener,NULL);
    assert(wl_display_roundtrip(display)>=0 && ready);
}
static void metadata_exercise(int control) {
    bind_version=2;windows_scrgb=ready=false;
    struct wl_display *display=wl_display_connect(NULL);assert(display);
    struct wl_registry *registry=wl_display_get_registry(display);
    wl_registry_add_listener(registry,&registry_listener,NULL);
    assert(wl_display_roundtrip(display)>=0);assert(wl_display_roundtrip(display)>=0);
    assert(manager && compositor && shm && output && windows_scrgb);
    struct wp_color_management_output_v1 *color_output=wp_color_manager_v1_get_output(manager,output);
    wp_color_management_output_v1_add_listener(color_output,&output_listener,NULL);
    struct wp_image_description_v1 *original=wp_color_management_output_v1_get_image_description(color_output);
    wait_ready(display,original);inspect(display,original,604,603);
    struct wl_surface *surface=wl_compositor_create_surface(compositor);
    struct wp_color_management_surface_v1 *color=wp_color_manager_v1_get_surface(manager,surface);
    struct wp_color_management_surface_feedback_v1 *feedback=wp_color_manager_v1_get_surface_feedback(manager,surface);
    wp_color_management_surface_feedback_v1_add_listener(feedback,&feedback_listener,NULL);
    struct wp_image_description_v1 *scrgb=wp_color_manager_v1_create_windows_scrgb(manager);
    wait_ready(display,scrgb);
    int fd=memfd_create("hdr-protocol-test",MFD_CLOEXEC);assert(fd>=0);assert(!ftruncate(fd,8*8*4));
    uint32_t *pixels=mmap(NULL,8*8*4,PROT_WRITE,MAP_SHARED,fd,0);assert(pixels!=MAP_FAILED);
    for(int i=0;i<64;i++) pixels[i]=0xffffffff;
    struct wl_shm_pool *pool=wl_shm_create_pool(shm,fd,8*8*4);
    struct wl_buffer *buffer=wl_shm_pool_create_buffer(pool,0,8,8,8*4,WL_SHM_FORMAT_XRGB8888);
    wl_shm_pool_destroy(pool);munmap(pixels,8*8*4);close(fd);
    wp_color_management_surface_v1_set_image_description(color,scrgb,WP_COLOR_MANAGER_V1_RENDER_INTENT_PERCEPTUAL);
    wl_surface_attach(surface,buffer,0,0);wl_surface_damage(surface,0,0,8,8);wl_surface_commit(surface);
    assert(wl_display_roundtrip(display)>=0);
    struct wp_image_description_v1 *preferred=wp_color_management_surface_feedback_v1_get_preferred(feedback);
    wait_ready(display,preferred);inspect(display,preferred,604,603);wp_image_description_v1_destroy(preferred);
    int previous_preferred=preferred_changes;
    assert(write(control,"1",1)==1);
    while(output_changes==0 || preferred_changes==previous_preferred) assert(wl_display_dispatch(display)>=0);
    struct wp_image_description_v1 *updated=wp_color_management_output_v1_get_image_description(color_output);
    wait_ready(display,updated);inspect(display,updated,604,400);wp_image_description_v1_destroy(updated);
    preferred=wp_color_management_surface_feedback_v1_get_preferred(feedback);
    wait_ready(display,preferred);inspect(display,preferred,604,400);wp_image_description_v1_destroy(preferred);
    int previous_output=output_changes;previous_preferred=preferred_changes;
    assert(write(control,"2",1)==1);
    while(output_changes==previous_output || preferred_changes==previous_preferred) assert(wl_display_dispatch(display)>=0);
    updated=wp_color_management_output_v1_get_image_description(color_output);
    wait_ready(display,updated);inspect(display,updated,800,300);wp_image_description_v1_destroy(updated);
    preferred=wp_color_management_surface_feedback_v1_get_preferred(feedback);
    wait_ready(display,preferred);inspect(display,preferred,800,300);wp_image_description_v1_destroy(preferred);
    /* Existing descriptions remain immutable after target/reference changes. */
    inspect(display,original,604,603);wp_image_description_v1_destroy(original);
    wp_color_management_surface_v1_unset_image_description(color);wl_surface_commit(surface);
    assert(wl_display_roundtrip(display)>=0);assert(write(control,"3",1)==1);
    wp_image_description_v1_destroy(scrgb);wp_color_management_surface_feedback_v1_destroy(feedback);
    wp_color_management_surface_v1_destroy(color);wl_buffer_destroy(buffer);wl_surface_destroy(surface);
    wp_color_management_output_v1_destroy(color_output);wp_color_manager_v1_destroy(manager);
    wl_output_destroy(output);wl_shm_destroy(shm);wl_compositor_destroy(compositor);wl_registry_destroy(registry);
    wl_display_flush(display);wl_display_disconnect(display);
    puts("PASS: primary PQ10000/reference603, EDID target604, output+preferred updates, immutable descriptions and buffered scRGB set/unset");
}
int main(int argc, char **argv) {
    if(argc==3 && !strcmp(argv[1],"--metadata")) {
        metadata_exercise(atoi(argv[2]));return 0;
    }
    for (uint32_t version = 1; version <= 2; version++) {
        exercise(version, false);
        exercise(version, true);
    }
}
