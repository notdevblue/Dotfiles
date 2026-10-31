"""Proof that scenery is a glyph grid, selected RGB is character-only, and mouse handlers are absent."""
import unittest

import cairo

from ascii_wallpaper import Scene


def pixel(surface,x,y):
    surface.flush();i=int(y)*surface.get_stride()+int(x)*4
    return bytes(surface.get_data()[i:i+4])


class CompositionTests(unittest.TestCase):
    def test_background_is_independent_of_source_rgb(self):
        scene=Scene(1280,720)
        before=bytes(scene.base.get_data())
        replacement=cairo.ImageSurface(cairo.FORMAT_RGB24,scene.source.get_width(),scene.source.get_height())
        ctx=cairo.Context(replacement);ctx.set_source_rgb(1,0,0);ctx.paint()
        scene.source=replacement
        scene.cells=scene.build_grid()
        after=scene.paint_grid()
        self.assertEqual(before,bytes(after.get_data()),'Source RGB leaked into the scenery')
        kinds={c[2] for c in scene.cells}
        self.assertTrue({'sky','mountain','forest','village','lake','foreground','character'}<=kinds)
        text=scene.text()
        self.assertEqual(len(text.splitlines()),scene.rows)
        self.assertTrue(all(32<=ord(c)<=126 or c=='\n' for c in text))

    def test_selected_character_pixels_survive_but_foreground_is_not_raster(self):
        for width,height,points,background in [
            (3876,1624,[(.77,.34),(.86,.22),(.90,.74),(.94,.96)],(.12,.95)),
            (1624,3870,[(.66,.60),(.84,.55),(.82,.82),(.90,.96)],(.04,.94))]:
            with self.subTest(size=(width,height)):
                scene=Scene(width,height);scene.flakes=[]
                output=cairo.ImageSurface(cairo.FORMAT_ARGB32,width,height)
                scene.draw(cairo.Context(output),0)
                self.assertEqual(scene.source_scale,1)
                for u,v in points:
                    x,y=int(width*u),int(height*v)
                    self.assertEqual(pixel(scene.character,x,y)[3],255)
                    self.assertEqual(pixel(output,x,y),pixel(scene.source,x,y))
                x,y=int(width*background[0]),int(height*background[1])
                self.assertEqual(pixel(scene.character,x,y)[3],0)
                self.assertNotEqual(pixel(output,x,y),pixel(scene.source,x,y))

    def test_scene_fills_outputs_without_independently_positioned_cutout(self):
        for width,height in [(3440,1440),(1440,3440),(600,1000)]:
            with self.subTest(size=(width,height)):
                scene=Scene(width,height)
                self.assertLessEqual(scene.offset_x,0)
                self.assertLessEqual(scene.offset_y,0)
                self.assertGreaterEqual(scene.offset_x+scene.source.get_width()*scene.source_scale,width)
                self.assertGreaterEqual(scene.offset_y+scene.source.get_height()*scene.source_scale,height)
                self.assertFalse(hasattr(scene,'character_x'))
                for removed in ('pointer','water','click','motion','leave'):
                    self.assertFalse(hasattr(scene,removed),removed)



if __name__=='__main__':unittest.main()
