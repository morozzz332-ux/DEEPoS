#!/usr/bin/env python3
"""Tests for apps/updatr - A/B state bookkeeping and slot installation.

The semantics must match tools/update.py: a fresh slot boots with attempts=0,
every boot increments attempts, the 4th attempt on the same slot flips to the
other slot with rollback=true, "good" clears both.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
BIN = ROOT / "apps" / "updatr" / "updatr"

failures: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {extra}")
        failures.append(name)


def run(*args: str, expect: int = 0) -> subprocess.CompletedProcess:
    proc = subprocess.run([str(BIN), *args], capture_output=True, text=True)
    if proc.returncode != expect:
        print(f"  FAIL updatr {' '.join(args)} -> rc={proc.returncode} (want {expect})")
        print(proc.stdout[-400:])
        print(proc.stderr[-400:])
        failures.append(f"rc:{' '.join(args)}")
    return proc


def load(state_dir: pathlib.Path) -> dict:
    return json.loads((state_dir / "boot.json").read_text(encoding="utf-8"))


def main() -> int:
    print("updatr tests")
    if not BIN.is_file():
        print("  FAIL binary missing - run make -C apps/updatr")
        return 1

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="deepos-updatr-"))
    state = tmp / "data"
    try:
        out = run("--state", str(state), "status")
        st = json.loads(out.stdout)
        check("default slot is A", st["slot"] == "A", out.stdout)
        check("default attempts 0", st["attempts"] == 0)
        check("default no rollback", st["rollback"] is False)
        check("state not written on status", not (state / "boot.json").exists())

        out = run("--state", str(state), "decide")
        check("decide prints A", out.stdout.strip() == "A", out.stdout)

        for i in range(3):
            run("--state", str(state), "begin")
            st = load(state)
            check(f"attempt {i + 1} keeps slot A", st["slot"] == "A" and st["attempts"] == i + 1, str(st))
        run("--state", str(state), "begin")
        st = load(state)
        check("4th attempt switches to B", st["slot"] == "B", str(st))
        check("4th attempt sets rollback", st["rollback"] is True, str(st))
        check("4th attempt resets attempts", st["attempts"] == 0, str(st))
        check("generation bumped", st["generation"] >= 1, str(st))

        run("--state", str(state), "good")
        st = load(state)
        check("good clears rollback", st["rollback"] is False and st["attempts"] == 0, str(st))

        run("--state", str(state), "switch", "A")
        st = load(state)
        check("switch sets slot", st["slot"] == "A", str(st))

        bad = run("--state", str(state), "switch", "C", expect=3)
        check("bad slot rejected", bad.returncode == 3)

        # install into a regular file (stands in for /dev/mmcblk1p2)
        img = tmp / "rootfs.squashfs"
        payload = bytes(range(256)) * 40
        img.write_bytes(payload)
        target = tmp / "slot.img"
        target.write_bytes(b"\x00" * len(payload))
        out = run("--state", str(state), "install", "--slot", "B", "--file", str(img), "--dev", str(target))
        check("install writes payload", target.read_bytes() == payload, out.stdout)
        st = load(state)
        check("install selects slot", st["slot"] == "B", str(st))
        check("install resets attempts", st["attempts"] == 0, str(st))

        small = tmp / "small.img"
        small.write_bytes(b"\x00" * 16)
        bad = run("--state", str(state), "install", "--slot", "A", "--file", str(img),
                  "--dev", str(small), expect=4)
        check("too-small target refused", bad.returncode == 4)

        missing_args = run("--state", str(state), "install", "--slot", "A", expect=3)
        check("incomplete install rejected", missing_args.returncode == 3)

        # corrupted state must not crash: unknown values fall back to defaults
        (state / "boot.json").write_text("{not json", encoding="utf-8")
        out = run("--state", str(state), "status")
        check("corrupted state is tolerated", out.returncode == 0, out.stdout)
            # --- bootloader side of A/B: extlinux.conf must follow the slot -------------
        boot = tmp / "boot"
        (boot / "extlinux").mkdir(parents=True)
        conf = boot / "extlinux" / "extlinux.conf"
        sample = (
            "LABEL DEEPoS\n"
            "LINUX /KERNEL\n"
            "FDT /dtbs/rk3326-r36s-v20.dtb\n"
            "APPEND root=PARTLABEL=DEEPOS_A rootfstype=squashfs ro rootwait console=ttyS2,1500000n8\n"
        )
        conf.write_text(sample, encoding="utf-8")

        run("--state", str(state), "--boot", str(boot), "switch", "B")
        text = conf.read_text(encoding="utf-8")
        check("extlinux points to B", "root=PARTLABEL=DEEPOS_B" in text, text[:120])
        check("extlinux keeps other lines", "LINUX /KERNEL" in text and "console=ttyS2" in text)
        check("no temporary file", not (boot / "extlinux" / "extlinux.conf.tmp").exists())

        run("--state", str(state), "--boot", str(boot), "switch", "A")
        check("extlinux back to A", "root=PARTLABEL=DEEPOS_A" in conf.read_text(encoding="utf-8"))

        # 4th failed boot flips the slot and therefore the loader config too
        run("--state", str(state), "switch", "A")
        for _ in range(3):
            run("--state", str(state), "begin")
        before = conf.read_text(encoding="utf-8")
        proc = run("--state", str(state), "--boot", str(boot), "begin")
        after = conf.read_text(encoding="utf-8")
        check("rollback switched the slot", '"slot": "B"' in proc.stdout, proc.stdout[-120:])
        check("rollback rewrote extlinux",
              "root=PARTLABEL=DEEPOS_B" in after and before != after)

        # missing loader config: state is still saved, exit code is 2
        proc = subprocess.run([str(BIN), "--state", str(state), "--boot", str(tmp / "noboot"),
                               "switch", "A"], capture_output=True, text=True)
        check("missing extlinux is an error", proc.returncode == 2, f"rc={proc.returncode}")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        for f in failures:
            print(f"  {f}")
        print(f"FAIL  updatr: {len(failures)} failure(s)")
        return 1
    print("PASS  updatr: A/B state, rollback, switch, extlinux sync, install, error codes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
