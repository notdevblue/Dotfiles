"""Regressions for continuous composition, protected artwork and local input."""
import unittest

import cairo

from ascii_wallpaper import Scene


def pixel(surface, x, y):
    surface.flush()
    i = int(y) * surface.get_stride() + int(x) * 4
    return bytes(surface.get_data()[i:i + 4])


class CompositionTests(unittest.TestCase):
    def test_character_and_foreground_pixels_survive_texture_and_animation(self):
        for width, height, points in [
            (3876, 1624, [(.77,.34),(.86,.22),(.90,.74),(.96,.96),(.38,.99)]),
            (1624, 3870, [(.66,.60),(.84,.55),(.82,.82),(.90,.96),(.04,.94)])]:
            with self.subTest(orientation=(width, height)):
                scene = Scene(width, height)
                self.assertEqual(scene.source_scale, 1)
                self.assertEqual((scene.offset_x, scene.offset_y), (0, 0))
                self.assertGreater(len(scene.cells), 500)
                output = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
                scene.motion(width*.8, height*.7, 0)
                scene.click(width*.2, height*.81, 0)
                scene.draw(cairo.Context(output), 1)
                for u, v in points:
                    self.assertEqual(scene.region(u,v), 'protected')
                    x,y=int(width*u),int(height*v)
                    self.assertEqual(pixel(output,x,y), pixel(scene.source,x,y))

    def test_landscape_and_portrait_cover_the_entire_output(self):
        for width,height in [(3440,1440),(1440,3440),(1280,720),(600,1000)]:
            with self.subTest(size=(width,height)):
                scene=Scene(width,height)
                self.assertLessEqual(scene.offset_x,0)
                self.assertLessEqual(scene.offset_y,0)
                self.assertGreaterEqual(scene.offset_x+scene.source.get_width()*scene.source_scale,width)
                self.assertGreaterEqual(scene.offset_y+scene.source.get_height()*scene.source_scale,height)
                self.assertFalse(hasattr(scene,'character_x'), 'A separately positioned cutout reappeared')

    def test_ripples_reject_character_sky_and_snow_foreground(self):
        scene=Scene(3440,1440)
        def point(u,v):
            return (scene.offset_x+u*scene.source.get_width()*scene.source_scale,
                    scene.offset_y+v*scene.source.get_height()*scene.source_scale)
        for u,v in [(.84,.5),(.2,.2),(.3,.99),(.4,.65)]:
            self.assertFalse(scene.click(*point(u,v),0))
        self.assertTrue(scene.click(*point(.2,.84),0))
        self.assertEqual(len(scene.ripples),1)
        scene.resize(1440,3440)
        self.assertEqual(len(scene.ripples),0)


if __name__=='__main__':
    unittest.main()
