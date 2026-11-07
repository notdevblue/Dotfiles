/* Exercise production Vulkan blur offscreen, including HDR float16 values.
 * No physical output, DRM master, compositor session or user app is changed. */
#include <assert.h>
#include <fcntl.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <drm_fourcc.h>
#include <wayland-server-core.h>
#include <wlr/backend/headless.h>
#include <wlr/interfaces/wlr_buffer.h>
#include <wlr/render/allocator.h>
#include <wlr/render/drm_format_set.h>
#include <wlr/render/interface.h>
#include <wlr/render/vulkan.h>
#include <wlr/render/wlr_texture.h>
#include <wlr/util/log.h>
#define SIZE 64
struct pixels { struct wlr_buffer base; _Float16 rgba[SIZE*SIZE*4]; };
static void destroy(struct wlr_buffer *b) { wlr_buffer_finish(b); free(b); }
static bool begin(struct wlr_buffer *b, uint32_t flags, void **data,
 uint32_t *format, size_t *stride) {
 if (flags & WLR_BUFFER_DATA_PTR_ACCESS_WRITE) return false;
 *data=((struct pixels *)b)->rgba; *format=DRM_FORMAT_ABGR16161616F; *stride=SIZE*8; return true;
}
static void end(struct wlr_buffer *b) {}
static const struct wlr_buffer_impl impl={.destroy=destroy,.begin_data_ptr_access=begin,.end_data_ptr_access=end};
static struct wlr_texture *checker(struct wlr_renderer *r, float offset) {
 struct pixels *p=calloc(1,sizeof(*p)); assert(p);
 wlr_buffer_init(&p->base,&impl,SIZE,SIZE);
 for(int y=0;y<SIZE;y++) for(int x=0;x<SIZE;x++) {
  int i=(y*SIZE+x)*4; float v=((x+y)%2?4:0)+offset;
  p->rgba[i]=v; p->rgba[i+1]=v; p->rgba[i+2]=v; p->rgba[i+3]=1;
 }
 struct wlr_texture *t=wlr_texture_from_buffer(r,&p->base); assert(t);
 wlr_buffer_drop(&p->base); return t;
}
static void draw(struct wlr_render_pass *p,struct wlr_texture *t) {
 wlr_render_pass_add_texture(p,&(struct wlr_render_texture_options){
  .texture=t,.dst_box={0,0,SIZE,SIZE},.transfer_function=WLR_COLOR_TRANSFER_FUNCTION_EXT_LINEAR,
  .blend_mode=WLR_RENDER_BLEND_MODE_NONE,.filter_mode=WLR_SCALE_FILTER_NEAREST,
 });
}
static void readback(struct wlr_renderer *r,struct wlr_buffer *b,_Float16 *pixels) {
 struct wlr_texture *t=wlr_texture_from_buffer(r,b);assert(t);
 assert(wlr_texture_read_pixels(t,&(struct wlr_texture_read_pixels_options){
  .data=pixels,.format=DRM_FORMAT_ABGR16161616F,.stride=SIZE*8,
 }));wlr_texture_destroy(t);
}
int main(int argc,char **argv) {
 assert(argc==2);wlr_log_init(WLR_ERROR,NULL);
 int fd=open(argv[1],O_RDWR|O_CLOEXEC);assert(fd>=0);
 struct wl_display *display=wl_display_create();
 struct wlr_backend *backend=wlr_headless_backend_create(wl_display_get_event_loop(display));
 struct wlr_renderer *r=wlr_vk_renderer_create_with_drm_fd(fd);close(fd);assert(r);
 struct wlr_allocator *a=wlr_allocator_autocreate(backend,r);assert(a);
 const struct wlr_drm_format *fmt=wlr_drm_format_set_get(r->impl->get_render_formats(r),DRM_FORMAT_ABGR16161616F);
 assert(fmt);
 struct wlr_buffer *b=wlr_allocator_create_buffer(a,SIZE,SIZE,fmt);assert(b);
 struct wlr_color_transform *linear=wlr_color_transform_init_linear_to_inverse_eotf(WLR_COLOR_TRANSFER_FUNCTION_EXT_LINEAR);assert(linear);
 _Float16 values[SIZE*SIZE*4];
 for(int frame=0;frame<64;frame++) {
  float offset=frame%2?2:0;
  struct wlr_texture *t=checker(r,offset);
  struct wlr_render_pass *p=wlr_renderer_begin_buffer_pass(r,b,&(struct wlr_buffer_pass_options){.color_transform=linear,.background_blur=true});assert(p);
  draw(p,t);
  pixman_region32_t clip;pixman_region32_init_rect(&clip,15,17,29,22);
  assert(wlr_render_pass_add_background_blur(p,&(struct wlr_render_background_blur_options){.dst_box={9,11,40,36},.clip=&clip}));
  pixman_region32_fini(&clip);
  wlr_render_pass_add_rect(p,&(struct wlr_render_rect_options){.box={23,24,3,7},.color={0,0,1,1}});
  assert(wlr_render_pass_submit(p));readback(r,b,values);
  for(int y=0;y<SIZE;y++) for(int x=0;x<SIZE;x++) {
   float expected=((x+y)%2?4:0)+offset;
   if(x>=15&&x<44&&y>=17&&y<39) expected=2+offset;
   bool foreground=x>=23&&x<26&&y>=24&&y<31;
   int i=(y*SIZE+x)*4;
   float red=foreground?0:expected,blue=foreground?1:expected;
   if(fabs((float)values[i]-red)>0.015 || fabs((float)values[i+2]-blue)>0.015) {
    fprintf(stderr,"frame %d (%d,%d): %g/%g expected %g/%g\n",frame,x,y,(double)values[i],(double)values[i+2],(double)red,(double)blue);abort();
   }
  }
  wlr_texture_destroy(t);
 }
 /* Two checkpoints in one frame: the second sees earlier foreground; neither
  * checkpoint filters foreground submitted after it. */
 struct wlr_texture *t=checker(r,0);
 struct wlr_render_pass *p=wlr_renderer_begin_buffer_pass(r,b,&(struct wlr_buffer_pass_options){.color_transform=linear,.background_blur=true});assert(p);draw(p,t);
 assert(wlr_render_pass_add_background_blur(p,&(struct wlr_render_background_blur_options){.dst_box={0,0,48,48}}));
 wlr_render_pass_add_rect(p,&(struct wlr_render_rect_options){.box={24,24,16,16},.color={1,0,0,1}});
 assert(wlr_render_pass_add_background_blur(p,&(struct wlr_render_background_blur_options){.dst_box={16,16,48,48}}));
 wlr_render_pass_add_rect(p,&(struct wlr_render_rect_options){.box={30,30,2,2},.color={0,0,1,1}});
 assert(wlr_render_pass_submit(p));readback(r,b,values);
 assert(values[(30*SIZE+30)*4]==0&&values[(30*SIZE+30)*4+2]==1);
 assert(values[(24*SIZE+24)*4+1]>0&&values[(24*SIZE+24)*4+1]<2);
 wlr_texture_destroy(t);
 /* Without a requested FP16 path the operation is a no-op, not an illegal
  * suspension of a one-subpass render pass. */
 p=wlr_renderer_begin_buffer_pass(r,b,&(struct wlr_buffer_pass_options){.color_transform=linear});assert(p);
 assert(!wlr_render_pass_add_background_blur(p,&(struct wlr_render_background_blur_options){.dst_box={0,0,SIZE,SIZE}}));
 assert(wlr_render_pass_submit(p));
 /* New render targets exercise scratch ownership and small/odd dimensions. */
 const int sizes[][2]={{1,1},{3,5},{37,49},{64,33},{17,64}};
 t=checker(r,0);
 for(size_t i=0;i<sizeof(sizes)/sizeof(sizes[0]);i++) {
  struct wlr_buffer *resized=wlr_allocator_create_buffer(a,sizes[i][0],sizes[i][1],fmt);assert(resized);
  p=wlr_renderer_begin_buffer_pass(r,resized,&(struct wlr_buffer_pass_options){.color_transform=linear,.background_blur=true});assert(p);draw(p,t);
  assert(wlr_render_pass_add_background_blur(p,&(struct wlr_render_background_blur_options){.dst_box={0,0,SIZE,SIZE}}));
  assert(wlr_render_pass_submit(p));readback(r,resized,values);
  assert(isfinite((float)values[0]));
  wlr_buffer_drop(resized);
 }
 wlr_texture_destroy(t);
 wlr_color_transform_unref(linear);wlr_buffer_drop(b);
 wlr_allocator_destroy(a);wlr_renderer_destroy(r);wlr_backend_destroy(backend);wl_display_destroy(display);
 puts("PASS: FP16 checker blur, values >1, exact clipping, foreground, two scene-prefix checkpoints, 64 reused-buffer frames, odd/small target recreation, disabled no-op");
}
