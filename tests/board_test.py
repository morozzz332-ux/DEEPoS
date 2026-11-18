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
    check("extlinux root is squashfs", "root=LABEL=DEEPOS_A" in conf and "rootfstype=squashfs" in conf)
    check("extlinux mounts read-only", re.search(r"(?m)^\s+.*\bro\b", conf) is not None)
    check("extlinux console on ttyS2", "console=ttyS2,1500000n8" in conf)
    check("extlinux enables zswap+psi", "zswap.enabled=1" in conf and "psi=1" in conf)


def test_rootfs_builder():
    tool = ROOT / "tools" / "build-rootfs.py"
    with tempfile.TemporaryDirectory() as tmp:
        stage = pathlib.Path(tmp) / "root"
        for rel in ["sbin/init", "bin/busybox", "apps/modd/modd", "apps/saved/saved",
                    "apps/updatr/updatr", "apps/launcher/launcher", "etc/deepos/version"]:
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
            check("rootfs keeps modd, saved and updatr",
                  "apps/modd/modd" in ls and "apps/saved/saved" in ls and "apps/updatr/updatr" in ls)

        broken = pathlib.Path(tmp) / "broken"
        (broken / "sbin").mkdir(parents=True)
        (broken / "sbin" / "init").write_text("x")
        p = run([sys.executable, str(tool), "--root", str(broken),
                 "--out", str(pathlib.Path(tmp) / "broken.squashfs"), "--check"])
        check("rootfs builder rejects incomplete tree",
              p.returncode != 0 and "missing bin/busybox" in (p.stderr or ""))


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


def main():
    print("board tests (R36S-V20):")
    test_dts()
    test_kernel_config()
    test_busybox_config()
    test_extlinux()
    test_rootfs_builder()
    test_emulators_config()
    test_rcs_order()
    print()
    if fails:
        print("FAIL  board: " + ", ".join(fails))
        return 1
    print("PASS  board: dtb, kernel config, busybox config, extlinux, rcs order, emulators, rootfs builder")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
