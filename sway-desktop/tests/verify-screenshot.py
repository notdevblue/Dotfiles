#!/usr/bin/env python3
"""Native regression checks in a private two-output Wayland compositor.

Requires Pillow, wtype, cc, wayland-scanner and the desktop capture dependencies.
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
            p = subprocess.Popen(
                [SCRIPT, "region"],
                env=env,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            children.append(p)
            # Wait for the selector's own layer, not an arbitrary freezer delay.
            wait(lambda: selector(p))
            time.sleep(0.15)
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
                    "cursor_excluded": True,
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
        print(
            json.dumps(
                {
                    "selections": records,
                    "cancel": True,
                    "interrupt_cleanup": True,
                    "full_mode": True,
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
