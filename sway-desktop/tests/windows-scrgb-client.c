/* Exercise the actual color-management wire protocol, including NVIDIA/Wine's
 * version-1 binding. Runs only against verify-hdr.py's isolated compositor. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <wayland-client.h>
#include "color-management-v1-client-protocol.h"

static struct wp_color_manager_v1 *manager;
static struct wl_compositor *compositor;
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
int main(void) {
    for (uint32_t version = 1; version <= 2; version++) {
        exercise(version, false);
        exercise(version, true);
    }
}
