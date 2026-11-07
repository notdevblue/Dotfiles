#!/usr/bin/env python3
"""Native regression checks in a private two-output Wayland compositor.

Requires Pillow, wtype, cc, wayland-scanner, Python GTK3/gtk-layer-shell
and the desktop capture dependencies.
Reuses the existing isolated environment and virtual pointer test device.
Never sends input to the real desktop or reads its screen/clipboard.
"""

import json
import os
import select
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from PIL import Image, ImageChops

DESKTOP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESKTOP.parent / "yuru"))
from verify_native import isolated_environment, stop_group

SCRIPT = str(DESKTOP / "config/sway/scripts/screenshot")
BINARY = Path(
    os.environ.get("GRIM_FREEZE_BINARY", Path.home() / ".local/lib/grim-freeze/grim")
).resolve()


def wait(probe, timeout=6):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = probe()
        if value:
            return value
        time.sleep(0.05)
    raise TimeoutError("test timed out")


def verify_wrapper_arguments():
    # Mixed-output IPC state is synthetic; commands never reach a compositor.
    with tempfile.TemporaryDirectory(prefix="screenshot-wrapper-") as name:
        temp = Path(name)
        env = dict(os.environ, HOME=name, XDG_RUNTIME_DIR=name)
        bindir = temp / "bin"
        bindir.mkdir()
        env['PATH'] = str(bindir) + ':' + env['PATH']
        calls = temp / 'calls.jsonl'
        fake = """#!/usr/bin/env python3
import json, sys
from pathlib import Path
name = Path(sys.argv[0]).name
root = Path.home()
if name == 'swaymsg':
    if sys.argv[-1] == 'get_outputs':
        print(json.dumps([{'name':'HDR-1','active':True,'power':True,'hdr':True,'sdr_white_level':603},
                          {'name':'SDR-2','active':True,'power':True,'hdr':False}]))
    else:
        print(json.dumps({'focused':True,'app_id':'fixture','rect':{'x':10,'y':20},
                          'window_rect':{'x':2,'y':3,'width':40,'height':50}}))
elif name == 'grim':
    with (root/'calls.jsonl').open('a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')
    Path(sys.argv[-1]).write_bytes(b'fake PNG payload')
elif name == 'wl-copy':
    (root/'clipboard').write_bytes(sys.stdin.buffer.read())
"""
        for command in ('swaymsg', 'wl-copy', 'notify-send'):
            file = bindir / command
            file.write_text(fake)
            file.chmod(0o755)
        binary = temp / '.local/lib/grim-freeze/grim'
        binary.parent.mkdir(parents=True)
        binary.write_text(fake)
        binary.chmod(0o755)
        for mode in ('region', 'window', 'full'):
            subprocess.run([SCRIPT, mode], env=env, check=True)
            assert (temp/'clipboard').read_bytes() == b'fake PNG payload'
        region, window, full = [json.loads(line) for line in calls.read_text().splitlines()]
        for arguments in (region, window, full):
            assert arguments[:2] == ['-H', 'HDR-1=603']
            assert '-c' not in arguments and 'SDR-2' not in ' '.join(arguments)
        assert region[2:-1] == ['-f']
        assert window[2:-1] == ['-g', '12,23 40x50']
        assert full[2:-1] == []


verify_wrapper_arguments()


with tempfile.TemporaryDirectory(prefix="screenshot-check-") as name:
    tmp = Path(name)
    env = isolated_environment(tmp)
    env["WLR_HEADLESS_OUTPUTS"] = "2"

    env["WLR_RENDERER"] = os.environ.get("SWAY_TEST_RENDERER", "pixman")
    children = []
    log = (tmp / "log").open("w+")
    try:
        bindir = tmp / "bin"
        bindir.mkdir()
        (bindir / "notify-send").write_text("#!/bin/sh\nexit 0\n")
        (bindir / "notify-send").chmod(0o755)
        env["PATH"] = str(bindir) + ":" + env["PATH"]
        (Path(env["HOME"]) / ".local/lib/grim-freeze").mkdir(parents=True)
        (Path(env["HOME"]) / ".local/lib/grim-freeze/grim").symlink_to(BINARY)
        config = tmp / "config"
        config.write_text(
            "xwayland disable\nseat seat0 fallback true\noutput HEADLESS-1 mode 800x600 position 0 0 bg #cc3311 solid_color\noutput HEADLESS-2 mode 800x600 transform 270 position 800 0 bg #22bb66 solid_color\n"
        )
        server = subprocess.Popen(
            [
                os.environ.get("SWAY_TEST_BINARY", "sway"),
                "--unsupported-gpu",
                "-c",
                str(config),
            ],
            env=env,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
        children.append(server)

        def ready():
            sockets = list(Path(env["XDG_RUNTIME_DIR"]).glob("sway-ipc.*.sock"))
            displays = [
                p
                for p in Path(env["XDG_RUNTIME_DIR"]).glob("wayland-*")
                if not p.name.endswith(".lock")
            ]
            if not sockets or not displays:
                return False
            env.update(SWAYSOCK=str(sockets[0]), WAYLAND_DISPLAY=displays[0].name)
            return (
                subprocess.run(
                    ["swaymsg", "-t", "get_outputs"], env=env, capture_output=True
                ).returncode
                == 0
            )

        wait(ready)
        keyboard = subprocess.Popen(
            ["wtype", "-s", "600000"],
            env=env,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
        children.append(keyboard)
        time.sleep(0.1)

        def run(args, **kwargs):
            return subprocess.run(
                args, env=env, check=True, capture_output=True, timeout=5, **kwargs
            )

        def sway(cmd):
            run(["swaymsg", "--", cmd])

        root = DESKTOP.parent / "yuru/tests"
        for mode, file in [
            ("client-header", "virtual-pointer.h"),
            ("private-code", "virtual-pointer.c"),
        ]:
            run(
                [
                    "wayland-scanner",
                    mode,
                    str(root / "wlr-virtual-pointer-unstable-v1.xml"),
                    str(tmp / file),
                ]
            )
        source = (
            (root / "ascii-pointer.c")
            .read_text()
            .replace(
                "while (wl_display_dispatch(display) >= 0) {}",
                """int x,y,b; while (scanf("%d %d %d", &x,&y,&b)==3) { zwlr_virtual_pointer_v1_motion_absolute(pointer,1,x,y,1400,800); if(b>=0) zwlr_virtual_pointer_v1_button(pointer,1,272,b); zwlr_virtual_pointer_v1_frame(pointer); wl_display_roundtrip(display); puts("done"); fflush(stdout); }""",
            )
        )
        (tmp / "pointer.c").write_text(source)
        run(
            [
                "cc",
                "-I",
                str(tmp),
                str(tmp / "pointer.c"),
                str(tmp / "virtual-pointer.c"),
                "-lwayland-client",
                "-o",
                str(tmp / "pointer"),
            ]
        )
        pointer = subprocess.Popen(
            [str(tmp / "pointer")],
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=log,
            start_new_session=True,
        )
        children.append(pointer)
        assert select.select([pointer.stdout], [], [], 3)[0]
        assert pointer.stdout.readline().strip() == b"ready"

        def mouse(x, y, b=-1):
            pointer.stdin.write(f"{x} {y} {b}\n".encode())
            pointer.stdin.flush()
            assert pointer.stdout.readline().strip() == b"done"
            time.sleep(0.03)

        def snap():
            run(["grim", str(tmp / "screen.png")])
            return Image.open(tmp / "screen.png").convert("RGB").copy()

        # Asymmetric pattern detects incorrect orientation on the rotated monitor.
        im = Image.new("RGB", (800, 600), "#cc3311")
        from PIL import ImageDraw

        draw = ImageDraw.Draw(im)
        draw.rectangle((40, 60, 500, 260), fill="#22aaee")
        draw.rectangle((500, 300, 760, 570), fill="#eeee33")
        im.save(tmp / "pattern.png")
        sway(f"output * bg {tmp}/pattern.png stretch")
        time.sleep(0.25)
        original = snap()

        def selector(p):
            processes = [
                line.split(None, 2)
                for line in subprocess.check_output(
                    ["ps", "-eo", "pid=,ppid=,comm="], text=True
                ).splitlines()
            ]
            owned = {str(p.pid)}
            for _ in range(5):
                owned.update(pid for pid, ppid, comm in processes if ppid in owned)
            return any(pid in owned and comm == "grim" for pid, ppid, comm in processes)

        def begin():
            before_pixel = snap().getpixel((10, 10))
            p = subprocess.Popen(
                [SCRIPT, "region"],
                env=env,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            children.append(p)
            # A process can still be preparing its buffers. Wait until the
            # selection overlay has actually painted its dimmed background.
            wait(lambda: selector(p) and snap().getpixel((10, 10)) != before_pixel)
            return p

        screenshots = Path(env["HOME"]) / "Pictures/Screenshots"
        records = []
        for i, (start, end) in enumerate(
            [((80, 100), (420, 240)), ((850, 100), (1200, 400))]
        ):
            mouse(start[0] + 20, start[1] + 20)
            p = begin()
            a = snap()
            sway("output * bg #103050 solid_color")
            time.sleep(0.3)
            b = snap()
            assert ImageChops.difference(a, b).getbbox() is None, (
                "selection background changed"
            )
            # Repeated invocation must exit without replacing the original frame.
            run([SCRIPT, "region"])
            x, y = start
            u, v = end
            mouse(x, y)
            mouse(x, y, 1)
            mouse(u, v)
            time.sleep(0.1)
            mouse(u, v, 0)
            assert p.wait(timeout=5) == 0, log.read()
            file = max(screenshots.glob("*.png"))
            assert Image.open(file).info.get("srgb") == 0, "missing sRGB PNG tag"
            saved = Image.open(file).convert("RGB")
            assert saved.size in [(u - x, v - y), (u - x + 1, v - y + 1)], (
                saved.size,
                start,
                end,
            )
            assert (
                ImageChops.difference(
                    saved, original.crop((x, y, x + saved.width, y + saved.height))
                ).getbbox()
                is None
            ), "saved pixels differ from invocation frame"
            clip = run(["wl-paste", "--type", "image/png"]).stdout
            assert clip == file.read_bytes(), "clipboard differs"
            assert not list(Path(env["XDG_RUNTIME_DIR"]).glob("sway-screenshot.*"))
            records.append(
                {
                    "selection": i,
                    "frozen_pixels": True,
                    "saved_original_pixels": True,
                    "clipboard": True,
                }
            )
            sway(f"output * bg {tmp}/pattern.png stretch")
            time.sleep(0.25)
        p = begin()
        p.terminate()
        assert p.wait(timeout=5) == 143, p.returncode
        before = list(screenshots.glob("*.png"))
        p = begin()
        run(["wtype", "-k", "Escape"])
        assert p.wait(timeout=5) == 0
        assert list(screenshots.glob("*.png")) == before, "cancel saved a file"
        time.sleep(0.15)
        assert not selector(p), "orphan selector"
        assert not list(Path(env["XDG_RUNTIME_DIR"]).glob("sway-screenshot.*"))
        time.sleep(0.5)
        sway(f"bindsym --no-repeat Mod4+Shift+s exec {SCRIPT} region")
        before = list(screenshots.glob("*.png"))
        run(
            [
                "wtype",
                "-M",
                "logo",
                "-M",
                "shift",
                "-P",
                "s",
                "-s",
                "120",
                "-p",
                "s",
                "-m",
                "shift",
                "-m",
                "logo",
            ]
        )
        wait(lambda: selector(server))
        time.sleep(0.2)
        assert selector(server), "shortcut closed before drag"
        mouse(100, 100)
        mouse(100, 100, 1)
        mouse(300, 200)
        mouse(300, 200, 0)
        wait(lambda: len(list(screenshots.glob("*.png"))) == len(before) + 1)
        wait(lambda: not selector(server))
        # Existing full mode still saves and copies without a frozen overlay.
        full = subprocess.Popen(
            [SCRIPT, "full"], env=env, stdout=log, stderr=log, start_new_session=True
        )
        children.append(full)
        assert full.wait(timeout=5) == 0
        saved = Image.open(max(screenshots.glob("*.png"))).convert("RGB")
        assert saved.size == original.size
        full_file = max(screenshots.glob("*.png"))
        assert Image.open(full_file).info.get("srgb") == 0
        assert run(["wl-paste", "--type", "image/png"]).stdout == full_file.read_bytes()
        # Window mode uses the same client/PNG/clipboard path as full/region.
        window = subprocess.Popen(["/usr/bin/python3", "-c", """
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
w = Gtk.Window(title='capture-window-fixture')
w.set_default_size(240, 160)
w.show_all()
Gtk.main()
"""], env=env, stdout=log, stderr=log, start_new_session=True)
        children.append(window)
        def find_window(node):
            if node.get('name') == 'capture-window-fixture': return node
            for child in node.get('nodes', []) + node.get('floating_nodes', []):
                found = find_window(child)
                if found: return found
        target = wait(lambda: find_window(json.loads(run(["swaymsg", "-t", "get_tree", "-r"]).stdout)))
        sway(f'[con_id={target["id"]}] focus')
        run([SCRIPT, "window"])
        window_file = max(screenshots.glob("*.png"))
        window_image = Image.open(window_file)
        assert window_image.size == (target['window_rect']['width'], target['window_rect']['height'])
        assert window_image.info.get('srgb') == 0
        assert run(["wl-paste", "--type", "image/png"]).stdout == window_file.read_bytes()
        stop_group(window)
        # A visible client-owned cursor is required: a pointer device alone
        # has no cursor sprite in a headless compositor.
        fixture_code = """
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GdkPixbuf, GtkLayerShell
css = Gtk.CssProvider()
css.load_from_data(b'window { background: #214365; }')
Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, 800)
pixels = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 24, 24)
pixels.fill(0xff00ffff)
cursor = Gdk.Cursor.new_from_pixbuf(Gdk.Display.get_default(), pixels, 0, 0)
windows = []
for n in range(Gdk.Display.get_default().get_n_monitors()):
    window = Gtk.Window()
    GtkLayerShell.init_for_window(window)
    GtkLayerShell.set_namespace(window, 'screenshot-cursor-fixture')
    GtkLayerShell.set_monitor(window, Gdk.Display.get_default().get_monitor(n))
    GtkLayerShell.set_layer(window, GtkLayerShell.Layer.BOTTOM)
    GtkLayerShell.set_exclusive_zone(window, -1)
    for edge in (GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                 GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT):
        GtkLayerShell.set_anchor(window, edge, True)
    window.connect('realize', lambda w: w.get_window().set_cursor(cursor))
    window.show_all()
    windows.append(window)
Gtk.main()
"""
        fixture = subprocess.Popen(
            ["/usr/bin/python3", "-c", fixture_code],
            env=env,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
        children.append(fixture)
        wait(lambda: snap().getpixel((10, 10)) == (33, 67, 101))
        input_count = len(json.loads(run(["swaymsg", "-t", "get_inputs", "-r"]).stdout))
        cursor_checks = []
        for start, end in [((80, 100), (420, 240)), ((850, 100), (1200, 400))]:
            x, y = start
            u, v = end
            mouse(x + 20, y + 20)
            time.sleep(0.2)
            # Positive control: prove that a real cursor sprite is painted.
            # Software cursors can also remain in subsequent output readbacks.
            run(["grim", "-c", str(tmp / "with-cursor.png")])
            painted = Image.open(tmp / "with-cursor.png").convert("RGB")
            assert painted.getpixel((x + 25, y + 25)) == (255, 0, 255), (
                "cursor fixture is invisible"
            )
            p = begin()
            mouse(x, y)
            mouse(x, y, 1)
            mouse(u, v)
            mouse(u, v, 0)
            assert p.wait(timeout=5) == 0
            assert (
                len(json.loads(run(["swaymsg", "-t", "get_inputs", "-r"]).stdout))
                == input_count
            )
            file = max(screenshots.glob("*.png"))
            assert Image.open(file).info.get("srgb") == 0, "missing sRGB PNG tag"
            saved = Image.open(file).convert("RGB")
            expected = Image.new("RGB", saved.size, (33, 67, 101))
            assert ImageChops.difference(saved, expected).getbbox() is None, (
                "cursor pixels remain in frozen PNG"
            )
            assert run(["wl-paste", "--type", "image/png"]).stdout == file.read_bytes()
            cursor_checks.append(
                {
                    "position": [x + 20, y + 20],
                    "visible_cursor_control": True,
                    "saved_cursor_pixels": 0,
                    "clipboard_matches": True,
                }
            )
        print(
            json.dumps(
                {
                    "selections": records,
                    "cursor_checks": cursor_checks,
                    "cancel": True,
                    "interrupt_cleanup": True,
                    "full_mode": True,
                    "window_mode": True,
                    "srgb_png_tags": True,
                    "shortcut_press_release_drag": True,
                },
                indent=2,
            )
        )
    except BaseException:
        log.flush()
        print((tmp / "log").read_text()[-6500:])
        raise
    finally:
        for p in reversed(children):
            stop_group(p)
