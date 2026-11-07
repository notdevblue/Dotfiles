/* Offscreen Vulkan regression for wlroots SDR reference-white adjustment.
 * Uses a headless synthetic PQ output: no display server, physical output,
 * DRM master or session is opened. The render node is only used for buffers.
 */
#include <assert.h>
#include <fcntl.h>
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <drm_fourcc.h>
#include <wayland-server-core.h>
#include <wlr/backend/headless.h>
#include <wlr/interfaces/wlr_buffer.h>
#include <wlr/interfaces/wlr_output.h>
#include <wlr/render/allocator.h>
#include <wlr/render/vulkan.h>
#include <wlr/render/wlr_texture.h>
#include <wlr/types/wlr_scene.h>
#include <wlr/types/wlr_compositor.h>
#include <wlr/types/wlr_color_management_v1.h>
#include <wlr/util/log.h>

static const struct wlr_output_impl *headless_impl;
static bool (*headless_test)(struct wlr_output *, const struct wlr_output_state *);
static bool (*headless_commit)(struct wlr_output *, const struct wlr_output_state *);
static bool synthetic_test(struct wlr_output *out, const struct wlr_output_state *state) {
    struct wlr_output_state copy = *state;
    copy.committed &= ~WLR_OUTPUT_STATE_IMAGE_DESCRIPTION;
    const struct wlr_output_impl *impl=out->impl; out->impl=headless_impl;
    bool ok=headless_test(out, &copy); out->impl=impl; return ok;
}
static bool synthetic_commit(struct wlr_output *out, const struct wlr_output_state *state) {
    struct wlr_output_state copy = *state;
    copy.committed &= ~WLR_OUTPUT_STATE_IMAGE_DESCRIPTION;
    const struct wlr_output_impl *impl=out->impl; out->impl=headless_impl;
    bool ok=headless_commit(out, &copy); out->impl=impl; return ok;
}
struct pixels { struct wlr_buffer base; uint32_t pixel; };
static void pixels_destroy(struct wlr_buffer *base) {
    wlr_buffer_finish(base); free(base);
}
static bool pixels_begin(struct wlr_buffer *base, uint32_t flags, void **data,
        uint32_t *format, size_t *stride) {
    struct pixels *buf = (struct pixels *)base;
    if (flags & WLR_BUFFER_DATA_PTR_ACCESS_WRITE) return false;
    *data = &buf->pixel; *format = DRM_FORMAT_ARGB8888; *stride = 4; return true;
}
static void pixels_end(struct wlr_buffer *base) {}
static const struct wlr_buffer_impl pixels_impl = {
    .destroy = pixels_destroy, .begin_data_ptr_access = pixels_begin,
    .end_data_ptr_access = pixels_end,
};
static struct wlr_scene_buffer *pixel_node(struct wlr_scene *scene, uint8_t grey,
        enum wlr_color_transfer_function tf) {
    struct pixels *buf = calloc(1, sizeof(*buf));
    wlr_buffer_init(&buf->base, &pixels_impl, 1, 1);
    buf->pixel = 0xff000000u | grey * 0x010101u;
    struct wlr_scene_buffer *node = wlr_scene_buffer_create(&scene->tree, &buf->base);
    wlr_buffer_drop(&buf->base);
    wlr_scene_buffer_set_dest_size(node, 8, 8);
    wlr_scene_buffer_set_transfer_function(node, tf);
    wlr_scene_buffer_set_primaries(node, tf == WLR_COLOR_TRANSFER_FUNCTION_ST2084_PQ ?
        WLR_COLOR_NAMED_PRIMARIES_BT2020 : WLR_COLOR_NAMED_PRIMARIES_SRGB);
    return node;
}
/* Float16 keeps values above 1 and negative channels, as Wine's scRGB
 * swapchain does. Integer textures cannot expose accidental clipping. */
struct fpixels { struct wlr_buffer base; _Float16 rgba[4]; };
static bool fpixels_begin(struct wlr_buffer *base, uint32_t flags, void **data,
        uint32_t *format, size_t *stride) {
    if (flags & WLR_BUFFER_DATA_PTR_ACCESS_WRITE) return false;
    *data = ((struct fpixels *)base)->rgba;
    *format = DRM_FORMAT_ABGR16161616F; *stride = 8; return true;
}
static const struct wlr_buffer_impl fpixels_impl = {
    .destroy = pixels_destroy, .begin_data_ptr_access = fpixels_begin,
    .end_data_ptr_access = pixels_end,
};
static struct wlr_scene_buffer *float_node(struct wlr_scene *scene,
        float r, float g, float b) {
    struct fpixels *buf = calloc(1, sizeof(*buf));
    wlr_buffer_init(&buf->base, &fpixels_impl, 1, 1);
    buf->rgba[0]=r; buf->rgba[1]=g; buf->rgba[2]=b; buf->rgba[3]=1;
    struct wlr_scene_buffer *node = wlr_scene_buffer_create(&scene->tree, &buf->base);
    wlr_buffer_drop(&buf->base);
    wlr_scene_buffer_set_dest_size(node, 8, 8);
    wlr_scene_buffer_set_transfer_function(node, WLR_COLOR_TRANSFER_FUNCTION_EXT_LINEAR);
    wlr_scene_buffer_set_primaries(node, WLR_COLOR_NAMED_PRIMARIES_SRGB);
    wlr_scene_buffer_set_windows_scrgb(node, true);
    return node;
}
static uint32_t last_pixel;
static double pq_decode(double v) {
    const double m1=2610.0/16384, m2=2523.0/32, c1=3424.0/4096, c2=2413.0/128, c3=2392.0/128;
    double p=pow(v, 1/m2); return 10000 * pow(fmax(p-c1,0)/(c2-c3*p),1/m1);
}
static uint8_t frame(struct wlr_scene_output *so, float white, bool hdr, bool set_desc) {
    struct wlr_output_state state;
    wlr_output_state_init(&state);
    const struct wlr_output_image_description desc = {
        .primaries = WLR_COLOR_NAMED_PRIMARIES_BT2020,
        .transfer_function = WLR_COLOR_TRANSFER_FUNCTION_ST2084_PQ,
    };
    if (set_desc) assert(wlr_output_state_set_image_description(&state, hdr ? &desc : NULL));
    struct wlr_scene_output_state_options opts = {.sdr_white_level = white};
    assert(wlr_scene_output_build_state(so, &state, &opts));
    assert(state.buffer);
    struct wlr_texture *tex = wlr_texture_from_buffer(so->output->renderer, state.buffer);
    assert(tex);
    uint32_t pixels[64] = {0};
    assert(wlr_texture_read_pixels(tex, &(struct wlr_texture_read_pixels_options){
        .data = pixels, .format = DRM_FORMAT_ABGR8888, .stride = 8*4,
    }));
    wlr_texture_destroy(tex);
    assert(wlr_output_commit_state(so->output, &state));
    wlr_output_state_finish(&state);
    last_pixel = pixels[4*8+4];
    return last_pixel & 255;
}
static void near_nits(const char *name, uint8_t sample, double expected) {
    double actual = pq_decode(sample/255.0);
    printf("%s: byte=%u decoded=%.2f nits expected=%.2f\n", name, sample, actual, expected);
    assert(fabs(actual-expected) < (expected < 4 ? fmax(0.08, expected*0.06) : fmax(4, expected*0.035)));
}
/* Real protocol client + buffered surface, restricted to an anonymous socket.
 * The subprocess never connects to the user's Wayland session. */
static struct wlr_scene *protocol_scene;
static struct wlr_scene_surface *protocol_surface;
static struct wl_listener protocol_new_surface,protocol_commit,protocol_destroy;
static bool saw_scrgb,saw_unset;
static void protocol_surface_commit(struct wl_listener *listener,void *data) {
    if(protocol_surface->buffer->windows_scrgb) saw_scrgb=true;
    else if(saw_scrgb) {
        assert(protocol_surface->buffer->transfer_function==WLR_COLOR_TRANSFER_FUNCTION_GAMMA22);
        saw_unset=true;
    }
}
static void protocol_surface_destroy(struct wl_listener *listener,void *data) {
    wl_list_remove(&protocol_commit.link);wl_list_remove(&protocol_destroy.link);
    protocol_surface=NULL;
}
static void protocol_surface_create(struct wl_listener *listener,void *data) {
    struct wlr_surface *surface=data;
    protocol_surface=wlr_scene_surface_create(&protocol_scene->tree,surface);assert(protocol_surface);
    protocol_commit.notify=protocol_surface_commit;wl_signal_add(&surface->events.commit,&protocol_commit);
    protocol_destroy.notify=protocol_surface_destroy;wl_signal_add(&surface->events.destroy,&protocol_destroy);
}
static void protocol_metadata_test(struct wl_display *display,struct wlr_renderer *renderer,
        struct wlr_scene *scene,struct wlr_scene_output *so) {
    const char *client=getenv("SWAY_HDR_TEST_CLIENT");
    if(!client) {puts("Protocol target test requires SWAY_HDR_TEST_CLIENT (the builder sets it).");return;}
    assert(wlr_renderer_init_wl_shm(renderer,display));
    struct wlr_compositor *compositor=wlr_compositor_create(display,6,renderer);assert(compositor);
    protocol_scene=scene;protocol_new_surface.notify=protocol_surface_create;
    wl_signal_add(&compositor->events.new_surface,&protocol_new_surface);
    const enum wp_color_manager_v1_render_intent intents[]={WP_COLOR_MANAGER_V1_RENDER_INTENT_PERCEPTUAL};
    struct wlr_color_manager_v1 *manager=wlr_color_manager_v1_create(display,2,
        &(struct wlr_color_manager_v1_options){.features.windows_scrgb=true,
            .render_intents=intents,.render_intents_len=1});assert(manager);
    wlr_scene_set_color_manager_v1(scene,manager);
    struct wlr_scene_node *node;
    wl_list_for_each(node,&scene->tree.children,link) wlr_scene_node_set_enabled(node,false);
    wlr_output_lock_attach_render(so->output,true);
    struct wlr_output_image_description desc={.primaries=WLR_COLOR_NAMED_PRIMARIES_BT2020,
        .transfer_function=WLR_COLOR_TRANSFER_FUNCTION_ST2084_PQ,
        .mastering_luminance={.min=.005,.max=603.7},.sdr_white_level=603};
    wlr_color_primaries_from_named(&desc.mastering_display_primaries,WLR_COLOR_NAMED_PRIMARIES_SRGB);
    struct wlr_output_state state;wlr_output_state_init(&state);
    assert(wlr_output_state_set_image_description(&state,&desc));
    assert(wlr_output_commit_state(so->output,&state));wlr_output_state_finish(&state);
    wlr_output_create_global(so->output,display);
    int sockets[2],control[2];assert(!socketpair(AF_UNIX,SOCK_STREAM,0,sockets));assert(!pipe(control));
    struct wl_client *wl_client=wl_client_create(display,sockets[0]);assert(wl_client);
    pid_t child=fork();assert(child>=0);
    if(!child) {
        close(sockets[0]);close(control[0]);
        char socket_fd[32],control_fd[32];snprintf(socket_fd,sizeof(socket_fd),"%d",sockets[1]);
        snprintf(control_fd,sizeof(control_fd),"%d",control[1]);setenv("WAYLAND_SOCKET",socket_fd,1);
        execl(client,client,"--metadata",control_fd,NULL);_exit(127);
    }
    close(sockets[1]);close(control[1]);assert(fcntl(control[0],F_SETFL,O_NONBLOCK)>=0);
    int status=0;bool updated=false;alarm(20);
    for(;;) {
        assert(wl_event_loop_dispatch(wl_display_get_event_loop(display),10)>=0);
        wl_display_flush_clients(display);
        char stage;
        while(read(control[0],&stage,1)==1) {
            if(stage=='1') {
                assert(saw_scrgb && protocol_surface && protocol_surface->buffer->windows_scrgb);
                near_nits("Buffered protocol scRGB before target update",frame(so,603,true,false),80);
                desc.sdr_white_level=400;
                wlr_output_state_init(&state);assert(wlr_output_state_set_image_description(&state,&desc));
                assert(wlr_output_commit_state(so->output,&state));wlr_output_state_finish(&state);
                near_nits("Buffered protocol scRGB after reference-only update",frame(so,400,true,false),80);
            } else if(stage=='2') {
                desc.mastering_luminance.max=800;desc.sdr_white_level=300;
                wlr_output_state_init(&state);assert(wlr_output_state_set_image_description(&state,&desc));
                assert(wlr_output_commit_state(so->output,&state));wlr_output_state_finish(&state);
                near_nits("Buffered protocol scRGB after target update",frame(so,300,true,false),80);
                updated=true;
            }
        }
        pid_t done=waitpid(child,&status,WNOHANG);assert(done>=0);if(done==child) break;
    }
    alarm(0);close(control[0]);assert(WIFEXITED(status)&&WEXITSTATUS(status)==0);
    assert(updated&&saw_scrgb&&saw_unset);
    wl_list_remove(&protocol_new_surface.link);
    wlr_output_destroy_global(so->output);
    wlr_output_lock_attach_render(so->output,false);
    puts("PASS: committed target/reference updates refresh output and buffered surface feedback; scRGB luminance and unset reset remain correct.");
}

int main(int argc, char **argv) {
    wlr_log_init(WLR_ERROR, NULL);
    if (argc != 2) {
        fprintf(stderr, "Usage: sdr-white-pixels RENDER_NODE\n");
        return 2;
    }
    int fd=open(argv[1], O_RDWR|O_CLOEXEC);
    assert(fd>=0);
    struct wl_display *display=wl_display_create();
    struct wlr_backend *backend=wlr_headless_backend_create(wl_display_get_event_loop(display));
    struct wlr_renderer *renderer=wlr_vk_renderer_create_with_drm_fd(fd);
    close(fd); assert(renderer);
    struct wlr_allocator *allocator=wlr_allocator_autocreate(backend, renderer); assert(allocator);
    struct wlr_output *output=wlr_headless_add_output(backend,8,8);
    struct wlr_output_impl impl=*output->impl;
    const struct wlr_output_impl *original_impl=output->impl;
    headless_impl=original_impl; headless_test=impl.test; headless_commit=impl.commit;
    impl.test=synthetic_test; impl.commit=synthetic_commit;
    /* Headless helpers identify the backend by impl pointer, so keep that
     * identity during each backend callback (below wrappers). */
    assert(wlr_output_init_render(output,allocator,renderer));
    output->supported_primaries=WLR_COLOR_NAMED_PRIMARIES_BT2020;
    output->supported_transfer_functions=WLR_COLOR_TRANSFER_FUNCTION_ST2084_PQ;
    assert(wlr_backend_start(backend));
    struct wlr_output_state init; wlr_output_state_init(&init);
    wlr_output_state_set_enabled(&init,true);
    assert(wlr_output_commit_state(output,&init)); wlr_output_state_finish(&init);
    output->impl=&impl;
    wlr_output_lock_attach_render(output,true);
    struct wlr_scene *scene=wlr_scene_create();
    struct wlr_scene_output *so=wlr_scene_output_create(scene,output);
    const float white[4]={1,1,1,1};
    struct wlr_scene_rect *rect=wlr_scene_rect_create(&scene->tree,8,8,white);
    near_nits("SDR rect default",frame(so,0,true,true),203);
    near_nits("SDR rect 400",frame(so,400,true,false),400);
    assert(output->software_cursor_locks);
    near_nits("SDR rect back to 203",frame(so,203,true,false),203);
    assert(!output->software_cursor_locks);
    wlr_scene_node_set_enabled(&rect->node,false);
    struct wlr_scene_buffer *sdr=pixel_node(scene,255,WLR_COLOR_TRANSFER_FUNCTION_SRGB);
    near_nits("SDR texture 400",frame(so,400,true,false),400);
    sdr->is_single_pixel_buffer=true;
    for (int i=0; i<4; i++) sdr->single_pixel_buffer_color[i]=UINT32_MAX;
    wlr_scene_node_set_position(&sdr->node,1,0);
    wlr_scene_node_set_position(&sdr->node,0,0);
    near_nits("SDR single-pixel 400",frame(so,400,true,false),400);
    wlr_scene_node_set_enabled(&sdr->node,false);
    struct wlr_scene_buffer *pq=pixel_node(scene,173,WLR_COLOR_TRANSFER_FUNCTION_ST2084_PQ);
    double expected=pq_decode(173/255.0);
    near_nits("PQ default",frame(so,0,true,false),expected);
    near_nits("PQ SDR-white 400",frame(so,400,true,false),expected);
    near_nits("PQ SDR-white 100",frame(so,100,true,false),expected);
    pq->is_single_pixel_buffer=true;
    for (int i=0; i<3; i++) pq->single_pixel_buffer_color[i]=(uint32_t)((double)UINT32_MAX*173/255);
    pq->single_pixel_buffer_color[3]=UINT32_MAX;
    near_nits("PQ single-pixel 400",frame(so,400,true,false),expected);
    wlr_scene_node_set_enabled(&rect->node,true);
    wlr_scene_buffer_set_opacity(pq,0.5);
    near_nits("HDR alpha over SDR 400",frame(so,400,true,false),(expected+400)/2);
    near_nits("HDR alpha over SDR 203",frame(so,203,true,false),(expected+203)/2);
    wlr_scene_node_set_enabled(&pq->node,false);
    wlr_scene_node_set_enabled(&rect->node,false);
    struct wlr_scene_buffer *linear=pixel_node(scene,128,WLR_COLOR_TRANSFER_FUNCTION_EXT_LINEAR);
    uint8_t lin_default=frame(so,0,true,false),lin_boost=frame(so,400,true,false);
    printf("Extended linear invariant: %u -> %u\n",lin_default,lin_boost);
    assert(abs((int)lin_default-(int)lin_boost)<=1);
    /* Generic extended-linear keeps its existing relative-white semantics. */
    near_nits("Generic extended linear 0.502",lin_default,128.0/255*203);
    wlr_scene_node_set_enabled(&linear->node,false);
    const float scrgb_values[] = {0.01f, 1.0f, 2.5375f, 7.5375f};
    for (size_t i=0; i<sizeof(scrgb_values)/sizeof(scrgb_values[0]); i++) {
        float v=scrgb_values[i];
        struct wlr_scene_buffer *node=float_node(scene,v,v,v);
        near_nits("Windows scRGB float16 default",frame(so,0,true,false),v*80);
        near_nits("Windows scRGB float16 SDR-white 603",frame(so,603,true,false),v*80);
        near_nits("Windows scRGB float16 SDR-white 100",frame(so,100,true,false),v*80);
        if (i == 2) {
            /* A metadata-only change must damage the existing node and reset
             * Windows-scRGB scaling when the surface switches descriptions. */
            wlr_scene_buffer_set_windows_scrgb(node,false);
            near_nits("Generic extended linear after Windows scRGB",frame(so,603,true,false),v*203);
            wlr_scene_buffer_set_windows_scrgb(node,true);
            near_nits("Windows scRGB after generic extended linear",frame(so,603,true,false),v*80);
        }
        wlr_scene_node_destroy(&node->node);
    }
    struct wlr_scene_buffer *wide=float_node(scene,-0.1f,0.4f,1.2f);
    frame(so,603,true,false);
    /* sRGB -> BT.2020 absolute-colorimetric matrix. A negative red input
     * contributes to each channel before PQ clamps output, preserving gamut. */
    near_nits("Windows scRGB negative red preserved",last_pixel & 255,
        80*(-0.1*0.627404+0.4*0.329283+1.2*0.043313));
    near_nits("Windows scRGB green preserved",(last_pixel >> 8) & 255,
        80*(-0.1*0.069097+0.4*0.919540+1.2*0.011362));
    near_nits("Windows scRGB above-one blue preserved",(last_pixel >> 16) & 255,
        80*(-0.1*0.016391+0.4*0.088013+1.2*0.895595));
    wlr_scene_node_destroy(&wide->node);
    wlr_scene_node_set_enabled(&sdr->node,true);
    uint8_t sdr_default=frame(so,0,false,true),sdr_boost=frame(so,400,false,false);
    printf("SDR output invariant: %u -> %u\n",sdr_default,sdr_boost);
    assert(sdr_default==sdr_boost && sdr_default==255);
    assert(!output->software_cursor_locks);
    struct wlr_output_state invalid; wlr_output_state_init(&invalid);
    struct wlr_scene_output_state_options bad={.sdr_white_level=NAN};
    assert(!wlr_scene_output_build_state(so,&invalid,&bad));
    bad.sdr_white_level=-1; assert(!wlr_scene_output_build_state(so,&invalid,&bad));
    wlr_output_state_finish(&invalid);
    /* Verify SDR software cursor brightness on the same PQ target. */
    wlr_scene_node_set_enabled(&sdr->node,false);
    struct pixels *cursor_pixels=calloc(1,sizeof(*cursor_pixels));
    wlr_buffer_init(&cursor_pixels->base,&pixels_impl,1,1);
    cursor_pixels->pixel=0xffffffff;
    struct wlr_output_cursor *cursor=wlr_output_cursor_create(output);
    assert(wlr_output_cursor_set_buffer(cursor,&cursor_pixels->base,0,0));
    wlr_buffer_drop(&cursor_pixels->base);
    assert(wlr_output_cursor_move(cursor,4,4));
    near_nits("SDR cursor 400",frame(so,400,true,true),400);
    wlr_output_cursor_destroy(cursor);
    assert(output->software_cursor_locks==1);
    /* An opaque native PQ buffer remains eligible for direct scanout. */
    wlr_output_lock_attach_render(output,false);
    pixel_node(scene,173,WLR_COLOR_TRANSFER_FUNCTION_ST2084_PQ);
    struct wlr_output_state scanout; wlr_output_state_init(&scanout);
    struct wlr_scene_output_state_options scan_opts={.sdr_white_level=400};
    assert(wlr_scene_output_build_state(so,&scanout,&scan_opts));
    assert(scanout.buffer && scanout.buffer->width==1);
    puts("Native PQ direct scanout remains eligible.");
    wlr_output_state_finish(&scanout);
    /* Commit a description change while bypassing composition, then compose
     * again without another IMAGE_DESCRIPTION flag. The cached SDR gamma
     * transform must not survive on the PQ target (or vice versa). */
    for(int direction=0;direction<2;direction++) {
        struct wlr_scene_node *node;
        wl_list_for_each(node,&scene->tree.children,link) wlr_scene_node_set_enabled(node,false);
        wlr_output_lock_attach_render(output,true);
        pixel_node(scene,173,WLR_COLOR_TRANSFER_FUNCTION_ST2084_PQ);
        frame(so,203,direction!=0,true);
        wl_list_for_each(node,&scene->tree.children,link) wlr_scene_node_set_enabled(node,false);
        struct wlr_scene_buffer *native=pixel_node(scene,direction==0?173:128,
            direction==0?WLR_COLOR_TRANSFER_FUNCTION_ST2084_PQ:WLR_COLOR_TRANSFER_FUNCTION_GAMMA22);
        wlr_output_lock_attach_render(output,false);
        const struct wlr_output_image_description desc={.primaries=WLR_COLOR_NAMED_PRIMARIES_BT2020,
            .transfer_function=WLR_COLOR_TRANSFER_FUNCTION_ST2084_PQ};
        struct wlr_output_state transition;wlr_output_state_init(&transition);
        assert(wlr_output_state_set_image_description(&transition,direction==0?&desc:NULL));
        struct wlr_scene_output_state_options opts={.sdr_white_level=203};
        assert(wlr_scene_output_build_state(so,&transition,&opts));
        assert(transition.buffer && transition.buffer->width==1);
        assert(wlr_output_commit_state(output,&transition));wlr_output_state_finish(&transition);
        wlr_output_lock_attach_render(output,true);
        uint8_t value=frame(so,203,direction==0,false);
        if(direction==0) near_nits("Committed SDR->PQ scanout->composition",value,expected);
        else {printf("Committed PQ->SDR scanout->composition: %u expected 128\n",value);assert(abs(value-128)<=1);}
        wlr_scene_node_destroy(&native->node);
        wlr_output_lock_attach_render(output,false);
    }
    protocol_metadata_test(display,renderer,scene,so);
    wlr_scene_node_destroy(&scene->tree.node);
    assert(output->software_cursor_locks==0);
    output->impl=original_impl;
    wlr_backend_destroy(backend);
    wlr_allocator_destroy(allocator);
    wlr_renderer_destroy(renderer);
    wl_display_destroy(display);
    puts("All offscreen SDR-white regression checks passed.");
}
