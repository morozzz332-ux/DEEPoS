#!/usr/bin/env python3
"""Board-layer tests for the DEEPoS R36S-V20 port.

The tests run on the host (inside `deepos-build:local`) and cover everything
that can be validated without the console:

1. the board DTS compiles with dtc (using the stub SoC dtsi from
   tests/fixtures/dts) and keeps the expected hardware bindings;
2. the kernel config fragment carries every MVP driver and no banned bloat;
3. the BusyBox fragment enables the applets init and the modules rely on;
4. extlinux.conf boots /KERNEL with the board DTB and a squashfs root;
5. tools/build-rootfs.py packs a staging tree into a valid squashfs and
   rejects a broken tree.
"""

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BOARD = ROOT / "board" / "r36s-v20"
TESTS = ROOT / "tests"

CPP = ["gcc", "-E", "-P", "-w", "-Dlinux=linux", "-x", "assembler-with-cpp",
       "-I", str(TESTS / "fixtures" / "dts"), "-I", str(BOARD / "dts")]

fails = []


def check(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        fails.append(name)
    return ok


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def test_dts():
    dts = BOARD / "dts" / "rk3326-r36s-v20.dts"
    with tempfile.TemporaryDirectory() as tmp:
        pre = pathlib.Path(tmp) / "board.dts"
        dtb = pathlib.Path(tmp) / "board.dtb"
        p = run(CPP + [str(dts), "-o", str(pre)])
        check("dts preprocesses", p.returncode == 0, (p.stderr or "").strip()[:200])
        if p.returncode != 0:
            return
        p = run(["dtc", "-I", "dts", "-O", "dtb", "-o", str(dtb), str(pre)])
        check("dts compiles with dtc", p.returncode == 0, (p.stderr or "").strip()[:200])
        if p.returncode != 0:
            return
        dump = run(["dtc", "-I", "dtb", "-O", "dts", str(dtb)]).stdout

        expect = [
            ('"deepos,r36s-v20', "board compatible"),
            ('compatible = "sitronix,st7703"', "panel driver binding"),
            ("hactive = <0x280>", "panel width 640"),
            ("vactive = <0x1e0>", "panel height 480"),
            ("clock-frequency = <0x1c9c380>", "panel pixel clock 30 MHz"),
            ("compatible = \"gpio-keys\"", "gpio-keys node"),
            ("compatible = \"adc-joystick\"", "adc-joystick node"),
            ("compatible = \"adc-keys\"", "volume rocker on ADC"),
            ("compatible = \"rockchip,rk817\"", "PMIC node"),
            ("compatible = \"rockchip,rk817-battery\"", "fuel gauge node"),
            ("compatible = \"rockchip,rk817-charger\"", "charger node"),
            ("compatible = \"simple-battery\"", "battery cell description"),
            ("charge-full-design-microamp-hours = <0x3567e0>", "3500 mAh cell"),
            ("compatible = \"simple-audio-card\"", "sound card"),
            ("root=LABEL", "not a dtb property (sanity)"),
        ]
        for needle, name in expect[:-1]:
            check("dtb contains " + name, needle in dump, needle)

        # 18 physical buttons wired on gpio3 (D-pad, ABXY, shoulders, start/select/menu, FN)
        keys = len(re.findall(r"gpios = <0x[0-9a-f]+ 0x[0-9a-f]+ 0x0*1>;", dump))
        check("16 gpio buttons declared", keys >= 16, f"found {keys}")
        check("panel reset is GPIO3_B7 active-low", "reset-gpios = <0x07 0x0f 0x01>;" in dump)
        check("speaker control on gpio3 pin 7", "rockchip,spk-con-gpio = <0x07 0x07 0x00>;" in dump)


def test_kernel_config():
    text = (BOARD / "linux.config").read_text(encoding="utf-8")
    required = [
        "CONFIG_SQUASHFS=y", "CONFIG_SQUASHFS_ZSTD=y", "CONFIG_OVERLAY_FS=y",
        "CONFIG_ZRAM=y", "CONFIG_ZSWAP=y", "CONFIG_PSI=y", "CONFIG_MEMCG=y",
        "CONFIG_DRM_ROCKCHIP=y", "CONFIG_DRM_PANEL_SITRONIX_ST7703=y",
        "CONFIG_DRM_PANFROST=y", "CONFIG_BACKLIGHT_PWM=y",
        "CONFIG_KEYBOARD_GPIO=y", "CONFIG_KEYBOARD_ADC=y", "CONFIG_JOYSTICK_ADC=y",
        "CONFIG_ROCKCHIP_SARADC=y", "CONFIG_SND_SOC_RK817=y", "CONFIG_SND_SIMPLE_CARD=y",
        "CONFIG_MFD_RK8XX=y", "CONFIG_MFD_RK8XX_I2C=y", "CONFIG_REGULATOR_RK808=y", "CONFIG_CHARGER_RK817=y",
        "CONFIG_CPUFREQ_DT=y", "CONFIG_PM_DEVFREQ=y",
        "CONFIG_USB_DWC2=y", "CONFIG_USB_CONFIGFS_NCM=y", "CONFIG_USB_CONFIGFS_F_FS=y",
        "CONFIG_MMC_DW_ROCKCHIP=y", "CONFIG_EXFAT_FS=y", "CONFIG_VFAT_FS=y",
        "CONFIG_EXT4_FS=y", "CONFIG_SERIAL_8250_DW=y", "CONFIG_THERMAL_OF=y",
    ]
    missing = [s for s in required if s not in text]
    check("kernel config has all MVP drivers", not missing, ",".join(missing))

    banned = ["CONFIG_MODULES=y", "CONFIG_WIRELESS=y", "CONFIG_BT=y",
              "CONFIG_DEBUG_INFO=y", "CONFIG_KALLSYMS_ALL=y", "CONFIG_FB=y"]
    bad = [s for s in banned if s in text]
    check("kernel config has no bloat", not bad, ",".join(bad))

    pairs = {
        "CONFIG_MODULES=n": "modules off",
        "CONFIG_SQUASHFS_ZSTD=y": "zstd squashfs",
    }
    for key, name in pairs.items():
        check("kernel config: " + name, key in text)

    # no duplicate definitions with conflicting values
    seen = {}
    dup = []
    for line in text.splitlines():
        m = re.match(r"^(CONFIG_[A-Z0-9_]+)=(\S+)$", line.strip())
        if not m:
            continue
        name, val = m.groups()
        if name in seen and seen[name] != val:
            dup.append(name)
        seen[name] = val
    check("kernel config has no conflicting duplicates", not dup, ",".join(dup))


def test_busybox_config():
    text = (BOARD / "busybox.config").read_text(encoding="utf-8")
    required = ["CONFIG_INIT=y", "CONFIG_ASH=y", "CONFIG_MDEV=y", "CONFIG_MOUNT=y",
                "CONFIG_SWITCH_ROOT=y", "CONFIG_TAR=y", "CONFIG_GZIP=y",
                "CONFIG_GREP=y", "CONFIG_SED=y", "CONFIG_AWK=y", "CONFIG_FIND=y",
                "CONFIG_CUT=y", "CONFIG_SYNC=y", "CONFIG_POWEROFF=y", "CONFIG_UDHCPC=y"]
    missing = [s for s in required if s not in text]
    check("busybox config enables required applets", not missing, ",".join(missing))
    check("busybox: no cron/syslog bloat", "CONFIG_CROND=y" not in text and "CONFIG_SYSLOGD=y" not in text)


def test_extlinux():
    conf = (BOARD / "boot" / "extlinux" / "extlinux.conf").read_text(encoding="utf-8")
    check("extlinux has DEEPoS label", re.search(r"(?m)^LABEL\s+DEEPoS$", conf) is not None)
    check("extlinux boots /KERNEL", re.search(r"(?m)^\s*LINUX\s+/KERNEL$", conf) is not None)
    check("extlinux uses board dtb", "FDT /dtbs/rk3326-r36s-v20.dtb" in conf)
    check("extlinux root is the A slot label", "root=PARTLABEL=DEEPOS_A" in conf)
    check("extlinux rootfstype is squashfs", "rootfstype=squashfs" in conf)
    check("no label-based root (needs an initramfs we do not ship)", "root=LABEL=" not in conf)
    check("extlinux mounts read-only", re.search(r"(?m)^\s+.*\bro\b", conf) is not None)
    check("extlinux console on ttyS2", "console=ttyS2,1500000n8" in conf)
    check("extlinux enables zswap+psi", "zswap.enabled=1" in conf and "psi=1" in conf)


def test_rootfs_builder():
    tool = ROOT / "tools" / "build-rootfs.py"
    with tempfile.TemporaryDirectory() as tmp:
        stage = pathlib.Path(tmp) / "root"
        for rel in ["sbin/init", "bin/busybox", "apps/modd/modd", "apps/saved/saved",
                    "apps/updatr/updatr", "apps/launcher/launcher",
                    "apps/playdemo/playdemo", "etc/deepos/version"]:
            p = stage / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("#!/bin/sh\nexit 0\n")
            p.chmod(0o755)
        out = pathlib.Path(tmp) / "rootfs.squashfs"
        p = run([sys.executable, str(tool), "--root", str(stage), "--out", str(out),
                 "--check", "--label", "DEEPOS_A"])
        check("rootfs builder packs squashfs", p.returncode == 0 and out.exists(),
              (p.stderr or "").strip()[:200])
        if out.exists():
            magic = out.read_bytes()[:4]
            check("rootfs has squashfs magic", magic == b"hsqs", magic.hex())
            ls = run(["unsquashfs", "-l", str(out)]).stdout
            check("rootfs keeps busybox and init", "sbin/init" in ls and "bin/busybox" in ls)
            check("rootfs keeps modd, saved, updatr and playdemo",
                  "apps/modd/modd" in ls and "apps/saved/saved" in ls and
                  "apps/updatr/updatr" in ls and "apps/playdemo/playdemo" in ls)

        broken = pathlib.Path(tmp) / "broken"
        (broken / "sbin").mkdir(parents=True)
        (broken / "sbin" / "init").write_text("x")
        p = run([sys.executable, str(tool), "--root", str(broken),
                 "--out", str(pathlib.Path(tmp) / "broken.squashfs"), "--check"])
        check("rootfs builder rejects incomplete tree",
              p.returncode != 0 and "missing bin/busybox" in (p.stderr or ""))


def test_partition_mounts():
    """rcS must mount BOOT, DATA and ROMS; system slots stay unmounted."""
    text = (ROOT / "board/r36s-v20/rootfs-overlay/etc/init.d/rcS").read_text(encoding="utf-8")
    check("rcS mounts BOOT at /flash", "mmcblk1p1 /flash" in text)
    check("rcS mounts DATA at /data", "mmcblk1p4 /data" in text)
    check("rcS mounts ROMS at /storage", "mmcblk1p5 /storage" in text)
    check("rcS does not mount SYS_B as /data", "mmcblk1p3 /data" not in text)
    check("rcS does not mount DATA as /storage", "mmcblk1p4 /storage" not in text)
    check("modd modules live on DATA", "/data/modules" in text)
    check("modd data lives on DATA", "/data/module-data" in text)


def test_rcs_robustness():
    """Boot must survive a missing card / re-exec: no set -e, best-effort mounts."""
    text = (ROOT / "board/r36s-v20/rootfs-overlay/etc/init.d/rcS").read_text(encoding="utf-8")
    check("rcS never aborts the boot", not any(l.strip() == "set -e" for l in text.splitlines()))
    check("rcS creates /data/config", "/data/config" in text)
    check("rcS creates /data/saves", "/data/saves" in text)
    check("rcS guards A/B on a real mount", "is_mounted /data" in text)
    check("rcS has mount helper", "mount_part()" in text)
    check("rcS skips already mounted dirs", '/proc/mounts' in text)
    for line in text.splitlines():
        if line.startswith("mount -t ") or line.startswith("mount -o "):
            check(f"mount is best-effort: {line.strip()[:40]}", "|| true" in line)
    pat = subprocess.run(
        ["sh", "-n", str(ROOT / "board/r36s-v20/rootfs-overlay/etc/init.d/rcS")],
        capture_output=True,
        text=True,
    )
    check("rcS parses as POSIX sh", pat.returncode == 0, pat.stderr)


def test_boot_handover():
    """rcS reports readiness and init respawns the launcher in the foreground."""
    rc = (ROOT / "board/r36s-v20/rootfs-overlay/etc/init.d/rcS").read_text(encoding="utf-8")
    init = (ROOT / "board/r36s-v20/rootfs-overlay/etc/inittab").read_text(encoding="utf-8")
    check("rcS reports storage/data readiness", "DEEPoS: storage=" in rc)
    check("inittab starts the launcher", "::respawn:/usr/bin/launcher" in init)
    check("inittab boots via rcS", "::sysinit:/etc/init.d/rcS" in init)
    check("inittab umounts on shutdown", "::shutdown:" in init)
    for rel in ("etc/init.d/rcS", "etc/inittab", "etc/os-release"):
        p = ROOT / "board/r36s-v20/rootfs-overlay" / rel
        check(f"overlay has {rel}", p.exists())
    rc_mode = (ROOT / "board/r36s-v20/rootfs-overlay/etc/init.d/rcS").stat().st_mode
    check("rcS is executable", bool(rc_mode & 0o111), oct(rc_mode))

    # Debug UART: without a getty on ttyS2 a boot failure is a black screen.
    check("inittab spawns getty on ttyS2",
          "ttyS2::respawn:/sbin/getty" in init and "1500000" in init)
    passwd = (ROOT / "board/r36s-v20/rootfs-overlay/etc/passwd").read_text(encoding="utf-8")
    check("passwd has root with shell", "root:" in passwd and "/bin/sh" in passwd)
    group = (ROOT / "board/r36s-v20/rootfs-overlay/etc/group").read_text(encoding="utf-8")
    check("group has root", "root:" in group)
    bb = (ROOT / "board/r36s-v20/busybox.config").read_text(encoding="utf-8")
    check("busybox getty enabled", "CONFIG_GETTY=y" in bb)
    check("busybox login enabled", "CONFIG_LOGIN=y" in bb)


def test_emulators_config():
    path = ROOT / "board" / "r36s-v20" / "data" / "emulators.toml"
    if not path.exists():
        check("emulators.toml", False, str(path))
        return
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    mappings = [ln for ln in lines if ln and not ln.startswith("#") and " = " in ln]
    check("emulators.toml mappings", len(mappings) >= 3, str(len(mappings)))
    check("emulators.toml %ROM%", all("%ROM%" in m for m in mappings),
          "; ".join(m for m in mappings if "%ROM%" not in m))


def test_rcs_order():
    """A/B bookkeeping must run before rcS exits, and BOOT must be mounted."""
    rcs = ROOT / "board" / "r36s-v20" / "rootfs-overlay" / "etc" / "init.d" / "rcS"
    text = rcs.read_text(encoding="utf-8")
    check("rcS exists", rcs.is_file())
    check("rcS mounts BOOT on /flash", "mmcblk1p1 /flash" in text)
    check("rcS passes --boot /flash", "--boot /flash" in text)
    exit_at = text.find("\nexit 0")
    begin_at = text.find("updatr --state /data --boot /flash begin")
    good_at = text.find("updatr --state /data --boot /flash good")
    check("A/B begin runs before exit 0",
          exit_at != -1 and begin_at != -1 and begin_at < exit_at,
          f"exit@{exit_at} begin@{begin_at}")
    check("A/B good scheduled before exit 0",
          exit_at != -1 and good_at != -1 and good_at < exit_at,
          f"exit@{exit_at} good@{good_at}")


def test_boot_report() -> None:
    text = (ROOT / "board/r36s-v20/rootfs-overlay/etc/init.d/rcS").read_text(encoding="utf-8")
    check("report dir on BOOT", "/flash/report" in text)
    check("report guarded by mount", "is_mounted /flash" in text)
    for name in ("boot.txt", "mounts.txt", "free.txt", "dmesg.txt",
                 "temps.txt", "cpufreq.txt", "modules.txt", "selftest.txt"):
        check(f"report writes {name}", name in text)
    check("report runs selftest", "--selftest" in text)
    check("report syncs", "sync 2>/dev/null" in text)
    # The report must not be able to abort the boot.
    for line in text.splitlines():
        if "$rep/" not in line:
            continue
        check(f"report line is best-effort: {line.strip()[:40]}",
              "|| true" in line)


def test_usb_gadget() -> None:
    overlay = ROOT / "board/r36s-v20/rootfs-overlay"
    gadget = overlay / "usr/local/bin/usb-gadget.sh"
    check("gadget script exists", gadget.exists())
    if gadget.exists():
        text = gadget.read_text(encoding="utf-8")
        check("gadget mounts configfs", "mount -t configfs" in text)
        check("gadget binds a UDC", "> UDC" in text or "echo \"$udc\" > UDC" in text)
        check("gadget has acm function", "functions/acm.gs0" in text)
        check("gadget has ncm function", "functions/ncm.usb0" in text)
        check("gadget assigns link-local ip", "169.254.170.2/16" in text)
        check("gadget is best-effort at boot", "|| true" in text)
    getty = overlay / "usr/local/bin/gadget-getty.sh"
    check("gadget getty helper exists", getty.exists())
    if getty.exists():
        gtext = getty.read_text(encoding="utf-8")
        check("getty waits for the node", "/dev/ttyGS0" in gtext)
        check("getty execs login", "getty -L /dev/ttyGS0" in gtext)
    inittab = (overlay / "etc/inittab").read_text(encoding="utf-8")
    check("inittab starts gadget getty", "ttyGS0::respawn:/usr/local/bin/gadget-getty.sh" in inittab)
    rcs = (overlay / "etc/init.d/rcS").read_text(encoding="utf-8")
    check("rcS calls the gadget script", "usb-gadget.sh" in rcs)
    conf = (ROOT / "board/r36s-v20/linux.config").read_text(encoding="utf-8")
    for sym in ("CONFIG_USB_CONFIGFS_ACM=y", "CONFIG_USB_CONFIGFS_NCM=y",
                "CONFIG_USB_F_ACM=y", "CONFIG_USB_F_NCM=y"):
        check(f"kernel has {sym}", sym in conf)


def test_selfcheck() -> None:
    script = ROOT / "board/r36s-v20/rootfs-overlay/usr/local/bin/selfcheck.sh"
    check("selfcheck exists", script.exists())
    if not script.exists():
        return
    text = script.read_text(encoding="utf-8")
    for key in ("kernel=", "verdict=", "panel=", "input_events=", "battery=",
                "charger=", "flash=", "data=", "roms=", "modd=", "launcher=",
                "mem_available_mb=", "soc_c="):
        check(f"selfcheck reports {key.rstrip('=')}", key in text)
    check("verdict fails without panel", 'verdict=FAIL' in text)
    check("checks /proc/mounts", "/proc/mounts" in text)
    check("selfcheck never aborts boot", "exit 0" in text)
    rcs = (ROOT / "board/r36s-v20/rootfs-overlay/etc/init.d/rcS").read_text(encoding="utf-8")
    check("rcS runs selfcheck", "selfcheck.sh /flash/report/checks.txt" in rcs)



def test_rcs_provisioning():
    rcs = (ROOT / "board/r36s-v20/rootfs-overlay/etc/init.d/rcS").read_text(
        encoding="utf-8")
    check("rcS provisions modules on first boot",
          "/usr/share/deepos/modules" in rcs and "[ ! -d /data/modules ]" in rcs)
    check("rcS provisions the demo port", "/usr/share/deepos/roms" in rcs)
    check("rcS applies saved settings at boot", "launcher --apply --data /data" in rcs)

    demo = ROOT / "board/r36s-v20/rootfs-overlay/usr/share/deepos/roms/ports/demo.sh"
    check("demo port shipped in the rootfs", demo.is_file())
    check("demo port is executable", demo.is_file() and (demo.stat().st_mode & 0o111) != 0)
    check("demo port starts playdemo",
          demo.is_file() and "/usr/bin/playdemo" in demo.read_text(encoding="utf-8"))

    table = (ROOT / "board/r36s-v20/data/emulators.toml").read_text(encoding="utf-8")
    check("ports are launched through the shell", "ports = " in table and "%ROM%" in table)


def main():
    print("board tests (R36S-V20):")
    test_dts()
    test_kernel_config()
    test_busybox_config()
    test_extlinux()
    test_rootfs_builder()
    test_emulators_config()
    test_rcs_provisioning()
    test_partition_mounts()
    test_rcs_robustness()
    test_boot_handover()
    test_boot_report()
    test_usb_gadget()
    test_selfcheck()
    test_rcs_order()
    print()
    if fails:
        print("FAIL  board: " + ", ".join(fails))
        return 1
    print("PASS  board: dtb, kernel config, busybox config, extlinux, mounts, handover, report, gadget, selfcheck, rcs order, emulators, rootfs builder")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
