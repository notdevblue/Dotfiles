#!/usr/bin/env python3
"""Build and run the offscreen Vulkan blur regression against a wlroots build.

Usage: verify-blur-pixels.py SOURCE_ROOT BUILD_ROOT [RENDER_NODE]
Works with standalone and Sway Meson subproject builds, static or shared.
Uses a DRM render node only: no real display output or session changes.
"""
import glob
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

if len(sys.argv) not in (3, 4):
    raise SystemExit(__doc__)
source, build = [Path(arg).resolve() for arg in sys.argv[1:3]]
if not (source / "include/wlr/types/wlr_scene.h").is_file():
    raise SystemExit(f"Not a wlroots source tree: {source}")
libs = [p for p in (build / "libwlroots-0.20.a", build / "libwlroots-0.20.so") if p.exists()]
if not libs:
    raise SystemExit(f"No built wlroots library in {build}")
library = libs[0]
env = os.environ.copy()
# Meson writes subproject pkg-config files beneath the top-level build root.
for root in [build, *build.parents]:
    pcdir = root / "meson-uninstalled"
    if (pcdir / "wlroots-0.20-uninstalled.pc").is_file():
        env["PKG_CONFIG_PATH"] = str(pcdir) + os.pathsep + env.get("PKG_CONFIG_PATH", "")
        break
else:
    raise SystemExit("Missing generated wlroots pkg-config metadata")
flags = shlex.split(subprocess.check_output(
    ["pkg-config", "--cflags", "--libs", "--static", "wlroots-0.20"], env=env, text=True))
# Link the exact build under test, even if a system wlroots is installed.
flags = [str(library) if flag == "-lwlroots-0.20" else flag for flag in flags]
render_node = (sys.argv[3] if len(sys.argv) == 4 else
    env.get("SWAY_TEST_RENDER_NODE") or env.get("WLR_RENDER_DRM_DEVICE"))
if not render_node:
    render_node = next((p for p in sorted(glob.glob("/dev/dri/renderD*"))
        if os.access(p, os.R_OK | os.W_OK)), None)
if not render_node:
    raise SystemExit("No accessible DRM render node; set SWAY_TEST_RENDER_NODE")
compiler = shlex.split(env.get("CC", "cc"))
with tempfile.TemporaryDirectory(prefix="wlroots-blur-test-") as tmp:
    exe = Path(tmp) / "blur-pixels"
    command = compiler + ["-DWLR_USE_UNSTABLE", "-DWLR_PRIVATE=", "-Wall", "-Wextra",
        "-Wno-unused-parameter", "-I" + str(build / "include"), "-I" + str(source / "include"),
        str(Path(__file__).with_name("verify-blur-pixels.c")), "-o", str(exe)] + flags
    if library.suffix == ".so":
        command += ["-Wl,-rpath," + str(build)]
    subprocess.run(command, check=True, env=env)
    result = subprocess.run([str(exe), render_node], env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(result.stdout, end="")
    if result.returncode or any(marker in result.stdout for marker in
            ("SYNC-HAZARD", "VUID-", "Validation Error")):
        raise SystemExit("Blur pixel regression or Vulkan validation failed")
