#!/usr/bin/env python3
"""Host tests for the DEEPoS BOOT tree assembler and the A/B boot state.

Covers:
* tools/mkboot.py produces the layout extlinux expects (KERNEL, dtbs/, extlinux/),
  refuses a missing/too-small kernel and a wrong extlinux entry, and writes a
  manifest with sha256 of every file;
* tools/update.py implements the attempt/rollback contract: three failed boots
  flip to the other slot, `good` resets the counter, `switch` moves the slot.
"""

import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
MKBOOT = ROOT / "tools" / "mkboot.py"
UPDATE = ROOT / "tools" / "update.py"
EXTLINUX = ROOT / "board" / "r36s-v20" / "boot" / "extlinux" / "extlinux.conf"

fails = []


def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        fails.append(name)


def run(*args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True)


def fake_kernel(path, size=2 * 1024 * 1024):
    path.write_bytes(b"\x00" * size)
    return path


def test_mkboot():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        kernel = fake_kernel(tmp / "Image")
        dtb = tmp / "board.dtb"
        dtb.write_bytes(b"\xd0\x0d\xfe\xed" + b"\x00" * 1024)
        logo = tmp / "logo.bmp"
        logo.write_bytes(b"BM" + b"\x00" * 64)

        out = tmp / "boot"
        p = run(MKBOOT, "--kernel", kernel, "--dtb", dtb, "--out", out,
                "--extlinux", EXTLINUX, "--logo", logo, "--version", "0.1")
        check("mkboot builds boot tree", p.returncode == 0, (p.stderr or "").strip()[:200])
        check("kernel copied as KERNEL", (out / "KERNEL").is_file())
        check("dtb copied into dtbs/", (out / "dtbs" / "rk3326-r36s-v20.dtb").is_file())
        check("extlinux copied", (out / "extlinux" / "extlinux.conf").is_file())
        check("logo copied", (out / "logo.bmp").is_file())

        mf = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
        check("manifest lists kernel, dtb, extlinux, logo",
              set(mf["files"]) == {"KERNEL", "dtbs/rk3326-r36s-v20.dtb",
                                   "extlinux/extlinux.conf", "logo.bmp"})
        check("manifest sizes match", mf["sizes"]["KERNEL"] == kernel.stat().st_size)
        check("manifest has board and version",
              mf["board"] == "r36s-v20" and mf["version"] == "0.1")

        out_default = tmp / "boot-default"
        p = run(MKBOOT, "--kernel", kernel, "--dtb", dtb, "--out", out_default)
        check("default BOOT builds", p.returncode == 0, p.stderr)
        default = (out_default / "extlinux/extlinux.conf").read_text()
        check("default kernel root uses PARTLABEL", "root=PARTLABEL=DEEPOS_A" in default)

        broken = tmp / "multiline.conf"
        broken.write_text(
            "LABEL DEEPoS\nLINUX /KERNEL\nFDT /dtbs/rk3326-r36s-v20.dtb\n"
            "APPEND root=PARTLABEL=DEEPOS_A rootfstype=squashfs ro rootwait " + chr(92) +
            "\nconsole=ttyS2,1500000n8 console=tty0\n", encoding="utf-8")
        p = run(MKBOOT, "--kernel", kernel, "--dtb", dtb, "--out", tmp / "bad-multiline",
                "--extlinux", broken)
        check("mkboot rejects line continuation", p.returncode != 0)

        out_donor = tmp / "boot-donor"
        p = run(MKBOOT, "--kernel", kernel, "--dtb", dtb, "--out", out_donor,
                "--boot-script", ROOT / "board/r36s-v20/boot/boot.cmd")
        check("donor BOOT builds with boot.scr", p.returncode == 0, p.stderr)
        if p.returncode == 0:
            data = (out_donor / "boot.scr").read_bytes()
            manifest = json.loads((out_donor / "MANIFEST.json").read_text())
            check("donor boot.scr is a U-Boot script", data[:4] == bytes.fromhex("27051956")
                  and data[30] == 6 and b"/extlinux/extlinux.conf" in data)
            check("boot.scr digest recorded in manifest",
                  manifest["files"].get("boot.scr") == hashlib.sha256(data).hexdigest())

        profile = ROOT / "board/r36s-v20/boot/extlinux/archr-v20.conf"
        out_archr = tmp / "boot-archr"
        p = run(MKBOOT, "--kernel", kernel, "--dtb", dtb, "--out", out_archr,
                "--extlinux", profile)
        archive = out_archr / "ROOTDIR.CPIO"
        payload = archive.read_bytes() if archive.is_file() else b""
        check("Arch-R BOOT includes a newc /root mountpoint",
              p.returncode == 0 and payload.startswith(b"070701")
              and payload[110:115] == b"root\0"
              and int(payload[14:22], 16) == 0o40755
              and payload[54:62] == b"00000000" and b"TRAILER!!!\0" in payload)
        if archive.is_file():
            mf = json.loads((out_archr / "MANIFEST.json").read_text())
            check("mountpoint archive digest is recorded",
                  mf["files"].get(archive.name) == hashlib.sha256(payload).hexdigest())

        tiny = tmp / "tiny.img"
        tiny.write_bytes(b"\x00" * 1024)

        # --extra files land in BOOT and are listed in the manifest
        extra = tmp / "README-FIRST.txt"
        extra.write_text("put games into ROMS/\n", encoding="utf-8")
        out_extra = tmp / "boot-extra"
        p = run(MKBOOT, "--kernel", kernel, "--dtb", dtb, "--out", out_extra,
                "--extlinux", EXTLINUX, "--extra", extra, "--version", "9.9-test")
        check("mkboot accepts --extra", p.returncode == 0, (p.stderr or "").strip()[:200])
        check("extra file copied into BOOT", (out_extra / "README-FIRST.txt").is_file())
        manifest = json.loads((out_extra / "MANIFEST.json").read_text(encoding="utf-8"))
        check("extra file listed in manifest", "README-FIRST.txt" in manifest["files"])
        check("extra file sha256 recorded",
              manifest["files"].get("README-FIRST.txt") == hashlib.sha256(
                  extra.read_bytes()).hexdigest())

        p = run(MKBOOT, "--kernel", tiny, "--dtb", dtb, "--out", tmp / "boot2")
        check("mkboot refuses tiny kernel", p.returncode != 0 and "too small" in (p.stderr or ""))

        bad = tmp / "bad.conf"
        bad.write_text("LABEL Other\n", encoding="utf-8")
        p = run(MKBOOT, "--kernel", kernel, "--dtb", dtb, "--out", tmp / "boot3",
                "--extlinux", bad)
        check("mkboot refuses wrong extlinux", p.returncode != 0 and "extlinux.conf is missing" in (p.stderr or ""))


def upd(state, *args):
    p = run(UPDATE, "--state", state, *args)
    return p


def state_of(state):
    return json.loads((pathlib.Path(state) / "boot.json").read_text(encoding="utf-8"))


def test_update():
    with tempfile.TemporaryDirectory() as tmp:
        st = pathlib.Path(tmp)

        p = upd(st, "status")
        check("default slot is A", p.returncode == 0 and json.loads(p.stdout)["slot"] == "A")
        check("decide prints A", upd(st, "decide").stdout.strip() == "A")

        upd(st, "switch", "B")
        check("switch moves to B", state_of(st)["slot"] == "B" and state_of(st)["attempts"] == 0)

        for _ in range(3):
            upd(st, "begin")
        check("three attempts keep the slot", state_of(st)["slot"] == "B" and state_of(st)["attempts"] == 3)
        upd(st, "begin")
        after = state_of(st)
        check("fourth attempt rolls back to A", after["slot"] == "A" and after["rollback"] is True)
        check("rollback resets attempts", after["attempts"] == 0)
        check("rollback bumps generation", after.get("generation", 0) >= 1)

        upd(st, "switch", "B")
        upd(st, "begin")
        upd(st, "good")
        good = state_of(st)
        check("good clears attempts and rollback", good["attempts"] == 0 and good["rollback"] is False)

        (st / "boot.json").write_text("{not json", encoding="utf-8")
        p = upd(st, "status")
        check("corrupted state is reported", p.returncode != 0 and "corrupted" in (p.stderr or ""))


def main():
    print("boot tests (BOOT tree + A/B state):")
    test_mkboot()
    test_update()
    print()
    if fails:
        print("FAIL  boot: " + ", ".join(fails))
        return 1
    print("PASS  boot: mkboot layout/manifest and A/B attempt/rollback logic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
