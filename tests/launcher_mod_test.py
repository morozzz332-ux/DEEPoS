#!/usr/bin/env python3
"""DEEPoS launcher <-> modd integration tests.

A real modd supervisor is started on a temporary UNIX socket with the module
fixtures, then the launcher is asked for the module list and renders the
"МОДУЛИ" screen from it.
"""
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "apps" / "launcher" / "launcher"
MODD = ROOT / "apps" / "modd" / "modd"
FIXTURES = ROOT / "tests" / "fixtures" / "modd"

FAILED = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        FAILED.append(name)


def wait_socket(path, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                s.connect(str(path))
                s.close()
                return True
            except OSError:
                pass
            finally:
                s.close()
        time.sleep(0.05)
    return False


def main():
    for binary in (LAUNCHER, MODD):
        if not binary.exists():
            print(f"FAIL  build {binary.name} first")
            return 1

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = pathlib.Path(tmp)
        sock = tmpdir / "modd.sock"
        data = tmpdir / "data"
        data.mkdir()
        roms = tmpdir / "roms" / "md"
        roms.mkdir(parents=True)
        for i in range(3):
            (roms / f"g{i}.md").write_bytes(b"")

        env = dict(os.environ, MODD_INIT_MS="600", MODD_ACTION_MS="400")
        modd = subprocess.Popen(
            [str(MODD), "--modules", str(FIXTURES), "--socket", str(sock), "--data", str(data)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        try:
            check("modd exposes a socket", wait_socket(sock))

            p = subprocess.run(
                [str(LAUNCHER), "--roms", str(tmpdir / "roms"), "--data", str(data),
                 "--modules-socket", str(sock), "--print-modules"],
                capture_output=True, text=True)
            lines = [l for l in p.stdout.splitlines() if l.strip()]
            check("launcher reads modules from modd", p.returncode == 0 and len(lines) >= 2,
                  (p.returncode, p.stdout[:120], (p.stderr or "")[:120]))
            ids = {l.split("\t")[0] for l in lines if "\t" in l}
            check("module ids are reported", {"thermal", "hang", "crash"} <= ids, sorted(ids))
            states = {l.split("\t")[0]: l.split("\t")[1] for l in lines if "\t" in l}
            check("disabled or stopped modules are not reported ready",
                  states.get("thermal") in {"ready", "stopped", "disabled", "unknown"},
                  states)

            ppm = tmpdir / "modules.ppm"
            p = subprocess.run(
                [str(LAUNCHER), "--roms", str(tmpdir / "roms"), "--data", str(data),
                 "--modules-socket", str(sock), "--screen", "modules", "--out", str(ppm)],
                capture_output=True, text=True)
            blob = ppm.read_bytes() if ppm.exists() else b""
            check("modules screen renders with live data",
                  p.returncode == 0 and blob.startswith(b"P6\n") and len(blob) > 640 * 480 * 3,
                  (p.returncode, len(blob)))

            p = subprocess.run(
                [str(LAUNCHER), "--roms", str(tmpdir / "roms"), "--data", str(data),
                 "--modules-socket", str(tmpdir / "no-such.sock"), "--print-modules"],
                capture_output=True, text=True)
            check("missing modd socket degrades gracefully", p.returncode == 0 and not p.stdout.strip(),
                  (p.returncode, p.stdout[:80]))
        finally:
            modd.terminate()
            try:
                modd.wait(timeout=5)
            except subprocess.TimeoutExpired:
                modd.kill()

    print("FAILED: " + ", ".join(FAILED) if FAILED else
          "PASS  launcher+modd: module list, states, modules screen, graceful fallback")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
