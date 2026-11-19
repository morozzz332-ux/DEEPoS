#!/usr/bin/env python3
"""DEEPoS framebuffer output tests.

The device path is /dev/fb0 (DRM fbdev emulation, RGB565). On a host we let the
same code write into a regular file (ftruncate + mmap), which makes the blit
byte-comparable with the PPM render of the same state.
"""
import os
import pathlib
import signal
import struct
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BIN = ROOT / "apps" / "launcher" / "launcher"
W, H = 640, 480

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        FAILED.append(name)


def read_ppm(path):
    data = pathlib.Path(path).read_bytes()
    parts = data.split(b"\n", 3)
    if parts[0] != b"P6":
        raise ValueError("not a P6 PPM")
    w, h = map(int, parts[1].split())
    return w, h, parts[3]


def ppm_to_565(ppm):
    w, h, raw = ppm
    out = bytearray()
    for i in range(0, w * h * 3, 3):
        r, g, b = raw[i], raw[i + 1], raw[i + 2]
        v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        out += struct.pack("<H", v)
    return bytes(out)


def test_first_frame(tmpdir):
    source = BIN.parent / "src"
    launcher = tmpdir / "launcher-boot-test"
    wrappers = ("dp_display_open", "dp_display_present", "dp_display_close",
                "dp_input_open", "dp_input_poll", "access", "execl")
    cmd = ["cc", "-o", str(launcher), "-I", str(source),
           *(str(obj) for obj in sorted(source.glob("*.o"))),
           str(ROOT / "tests" / "fixtures" / "launcher_boot.c"),
           *(f"-Wl,--wrap={name}" for name in wrappers)]
    build = subprocess.run(cmd, capture_output=True, text=True)
    if build.returncode != 0:
        check("launcher boot test links", False, build.stderr)
        return
    for mode, args, rc, confirmed in (
        ("hardware", [], 0, True),
        ("missing", [], 0, False),
        ("crash", [], -signal.SIGKILL, False),
        ("fail", [], 1, False),
        ("fake", [], 0, False),
        ("hardware", ["--out", str(tmpdir / "boot-test.ppm")], 0, False),
        ("hardware", ["--selftest"], 0, False),
    ):
        p = subprocess.run([str(launcher), *args], capture_output=True, text=True,
                           timeout=10, env={**os.environ, "DEEPOS_TEST_FRAMEBUFFER": mode})
        refreshed = "boot report refresh requested" in p.stdout
        logged = ("DEEPoS: launcher first frame\nboot report refresh requested\n"
                  "boot confirmation requested\n") in p.stdout
        check(f"boot confirmation ({mode}, {args[:1]})",
              p.returncode == rc and refreshed == logged == confirmed and
              (confirmed or "boot confirmation requested" not in p.stdout),
              (p.returncode, p.stdout, p.stderr))

    data = tmpdir / "physical-data"
    data.mkdir()
    config = data / "settings.toml"
    config.write_text("brightness = 20\n")
    result = subprocess.run(
        [str(launcher), "--screen", "settings", "--data", str(data),
         "--config", str(config), "--sysfs", str(tmpdir / "fake-sys")],
        capture_output=True, text=True, timeout=10,
        env={**os.environ, "DEEPOS_TEST_FRAMEBUFFER": "hardware",
             "DEEPOS_TEST_PHYSICAL_KEYS": "1"})
    check("physical Right/Right/A saves and applies the display setting",
          result.returncode == 0 and "brightness = 40" in config.read_text(),
          (result.returncode, result.stdout, result.stderr))


def main():
    if not BIN.exists():
        print(f"FAIL  build launcher first: {BIN}")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = pathlib.Path(tmp)
        roms = tmpdir / "roms" / "md"
        roms.mkdir(parents=True)
        for i in range(4):
            (roms / f"g{i}.md").write_bytes(b"")
        data = tmpdir / "data"
        data.mkdir()
        (data / "continue.tsv").write_text(
            "Sonic 3 & Knuckles\tMEGA DRIVE\t12 мин\t2\t1\n"
            "Lumines\tPSP\t46 мин\t-1\t0\n",
            encoding="utf-8")

        for screen in ("continue", "systems", "settings"):
            fb = tmpdir / f"{screen}.fb"
            ppm_path = tmpdir / f"{screen}.ppm"
            p = subprocess.run(
                [str(BIN), "--roms", str(tmpdir / "roms"), "--data", str(data),
                 "--screen", screen, "--out", str(ppm_path), "--fb", str(fb)],
                capture_output=True, text=True)
            blob = fb.read_bytes() if fb.exists() else b""
            check(f"{screen}: framebuffer has a full RGB565 frame",
                  p.returncode == 0 and len(blob) == W * H * 2,
                  (p.returncode, len(blob), (p.stderr or "")[-120:]))
            if len(blob) == W * H * 2 and ppm_path.exists():
                expected = ppm_to_565(read_ppm(ppm_path))
                check(f"{screen}: blit matches the rendered frame byte for byte", blob == expected,
                      next((i for i in range(min(len(blob), len(expected))) if blob[i] != expected[i]),
                           "len"))

        fb = tmpdir / "keys.fb"
        p = subprocess.run(
            [str(BIN), "--roms", str(tmpdir / "roms"), "--data", str(data),
             "--keys", "RIGHT", "--fb", str(fb)],
            capture_output=True, text=True)
        blob = fb.read_bytes() if fb.exists() else b""
        check("keys are applied before the frame is pushed", p.returncode == 0 and len(blob) == W * H * 2,
              (p.returncode, len(blob)))

        p = subprocess.run(
            [str(BIN), "--roms", str(tmpdir / "roms"), "--data", str(data),
             "--fb", str(tmpdir / "missing" / "x.fb")],
            capture_output=True, text=True)
        check("unusable framebuffer is reported", p.returncode == 1 and "no display" in (p.stderr or ""),
              (p.returncode, (p.stderr or "").strip()[-80:]))

        test_first_frame(tmpdir)

    print("FAILED: " + ", ".join(FAILED) if FAILED else
          "PASS  display: RGB565 blit, key-driven frames, error handling, boot confirmation")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
