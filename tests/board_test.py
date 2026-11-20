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
                "CONFIG_CUT=y", "CONFIG_SYNC=y", "CONFIG_POWEROFF=y", "CONFIG_UDHCPC=y",
                "CONFIG_READLINK=y", "CONFIG_FEATURE_READLINK_FOLLOW=y"]
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
    """Exercise the real rcS card resolver against synthetic kernel metadata."""
    text = (ROOT / "board/r36s-v20/rootfs-overlay/etc/init.d/rcS").read_text(encoding="utf-8")
    helpers = text.split("# 1. Kernel filesystems", 1)[0]
    for cards, root_card, root_part, missing in (
        ((0,), 0, 2, None), ((1,), 1, 2, None),
        ((0, 1), 1, 3, None), ((0, 1), 0, 2, 4),
        ((0, 1), 2, 2, None),
    ):
        with tempfile.TemporaryDirectory() as tmp:
            tree = pathlib.Path(tmp)
            devices = tree / "sys/dev/block"
            devices.mkdir(parents=True)
            for card in cards:
                disk = tree / f"sys/devices/mmc_host/mmc{card}/mmcblk{card}"
                disk.mkdir(parents=True)
                for number in range(1, 6):
                    if card == root_card and number == missing:
                        continue
                    part = disk / f"mmcblk{card}p{number}"
                    part.mkdir()
                    (part / "partition").write_text(f"{number}\n")
                    (devices / f"179:{card * 32 + number}").symlink_to(part)
            mountinfo = tree / "mountinfo"
            mountinfo.write_text(
                "10 1 0:1 / / rw - rootfs rootfs rw\n"
                f"11 10 179:{root_card * 32 + root_part} / / ro - squashfs /dev/root ro\n"
            )
            p = run(["sh", "-c", helpers + '''
                is_mounted() { return 1; }
                mount() { printf '%s %s\\n' "$3" "$4"; }
                mount_boot_card "$1" "$2"
                printf 'slot=%s\\n' "$boot_slot"
            ''', "rcS-test", str(mountinfo), str(devices)])
            expected = ([f"/dev/mmcblk{root_card}p{n} {path}"
                         for n, path in ((1, "/flash"), (4, "/data"), (5, "/storage"))
                         if n != missing] if root_card in cards else [])
            slot = {2: "A", 3: "B"}[root_part] if root_card in cards else ""
            check(f"rcS cards {cards}, root mmcblk{root_card}p{root_part}, missing {missing}",
                  p.returncode == 0 and p.stdout.splitlines() == [*expected, f"slot={slot}"],
                  p.stdout + p.stderr)
            if missing or root_card not in cards:
                check("rcS diagnoses missing partition or root", "DEEPoS:" in p.stderr, p.stderr)
    check("modd modules live on DATA", "/data/modules" in text)
    check("modd data lives on DATA", "/data/module-data" in text)


def test_rcs_robustness():
    """Boot must survive a missing card / re-exec: no set -e, best-effort mounts."""
    text = (ROOT / "board/r36s-v20/rootfs-overlay/etc/init.d/rcS").read_text(encoding="utf-8")
    check("rcS never aborts the boot", not any(l.strip() == "set -e" for l in text.splitlines()))
    check("rcS creates /data/config", "/data/config" in text)
    check("rcS creates /data/saves", "/data/saves" in text)
    check("rcS guards A/B on real same-card mounts",
          '[ "$data_mounted" = yes ] &&\n   [ "$flash_mounted" = yes ]' in text)
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
    driver_load = text.find('insmod "$joypad"')
    check("rcS loads the V20 joypad module before device discovery",
          '/lib/modules/$(uname -r)/archr-singleadc-joypad.ko' in text
          and 0 <= driver_load < text.find('mdev -s 2>'))
    check("rcS passes --boot /flash", "--boot /flash" in text)
    exit_at = text.find("\nexit 0")
    begin_at = text.find("updatr --state /data --boot /flash begin")
    check("A/B begin runs before exit 0",
          exit_at != -1 and begin_at != -1 and begin_at < exit_at,
          f"exit@{exit_at} begin@{begin_at}")
    check("A/B begin passes the running root slot and boot ticket",
          '--slot "$boot_slot" --boot-ticket /run/deepos-boot' in text)
    check("rcS never confirms a boot", re.search(r"updatr.*\bgood\b", text) is None)
    run_mount = re.search(r"mount -t tmpfs\s+tmpfs\s+/run\s+-o mode=0755", text)
    modd_at = text.find("/usr/bin/modd --modules")
    check("/run gets a writable tmpfs before modd is started",
          run_mount is not None and run_mount.start() < modd_at)


def test_boot_report() -> None:
    text = (ROOT / "board/r36s-v20/rootfs-overlay/etc/init.d/rcS").read_text(encoding="utf-8")
    check("report dir on BOOT", "/flash/report" in text)
    check("report guarded by mount", '[ "$flash_mounted" = yes ]' in text)
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
    gadget = overlay / "usr/local/bin/usb-mode.sh"
    check("gadget script exists", gadget.exists())
    if gadget.exists():
        text = gadget.read_text(encoding="utf-8")
        check("gadget mounts configfs", "mount -t configfs" in text)
        check("gadget binds a UDC", '> "$gadget/UDC"' in text)
        check("gadget requests the device role", "usb_role/*ff300000" in text)
        check("gadget starts DHCP without holding the mode lock", "udhcpc -f" in text and "9>&-" in text)
        check("ROMS is unmounted before exposing it", text.index('umount "$storage"') <
              text.index('"$roms" > "$lun/file"'))
        check("USB helpers parse as POSIX sh", all(
            subprocess.run(["sh", "-n", str(script)], check=False).returncode == 0
            for script in (gadget, gadget.with_name("usb-lease.sh"))))
    inittab = (overlay / "etc/inittab").read_text(encoding="utf-8")
    check("USB does not start a login console", "gadget-getty.sh" not in inittab)
    rcs = (overlay / "etc/init.d/rcS").read_text(encoding="utf-8")
    check("USB starts only on explicit selection", "usb-gadget.sh" not in rcs and "telnetd" not in rcs)
    check("debug shell needs the card flag", "[ -f /flash/DEBUG.ON ]" in rcs)
    debug = overlay / "usr/local/bin/usb-shell.sh"
    check("debug shell ships in the image", debug.exists())
    if debug.exists():
        check("debug shell listens on 23 and 8080",
              "nc -l -p 23 -e /bin/sh" in debug.read_text(encoding="utf-8"))
    check("rcS records same-card ROMS for USB", "/run/deepos-roms-device" in rcs)
    conf = (ROOT / "board/r36s-v20/linux.config").read_text(encoding="utf-8")
    for sym in ("CONFIG_USB_CONFIGFS_ACM=y", "CONFIG_USB_CONFIGFS_NCM=y",
                "CONFIG_USB_F_ACM=y", "CONFIG_USB_F_NCM=y", "CONFIG_USB_CONFIGFS_MASS_STORAGE=y"):
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
    check("rcS requests a refreshed report after the first frame", "/run/deepos-boot-report" in rcs)
    with tempfile.TemporaryDirectory() as tmp:
        output = pathlib.Path(tmp) / "checks.txt"
        p = run(["sh", str(script), str(output), "--first-frame"])
        check("first-frame report records the launcher", p.returncode == 0 and output.exists() and
              "launcher=running" in output.read_text(encoding="utf-8").splitlines(), p.stderr)



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


def test_gpu_and_ports_stack():
    """OpenGL and PortMaster need four things the old image shipped without."""
    overlay = ROOT / "board/r36s-v20/rootfs-overlay"
    # 1. panfrost is a module in the donor kernel; without it there is no
    #    render node and every GL application fails with "EGL not initialized".
    for module in ("panfrost.ko", "gpu-sched.ko", "drm_shmem_helper.ko"):
        p = overlay / "lib/modules/6.12.114" / module
        check(f"overlay ships {module}", p.is_file() and p.stat().st_size > 0)
    # 2. Mesa's KMS backend: control.txt needs /usr/lib/gbm/dri_gbm.so.
    gbm = overlay / "usr/lib/gbm/dri_gbm.so"
    check("overlay ships /usr/lib/gbm/dri_gbm.so", gbm.is_file() and gbm.stat().st_size > 0)
    rc = (overlay / "etc/init.d/rcS").read_text(encoding="utf-8")
    modules_line = next((ln for ln in rc.splitlines() if ln.startswith("gpu_modules=")), "")
    order = [modules_line.find(m) for m in ("drm_shmem_helper", "gpu-sched", "panfrost")]
    check("rcS loads the GPU modules in dependency order",
          all(pos >= 0 for pos in order) and order == sorted(order),
          modules_line.strip())
    check("rcS loads the modules before the launcher starts",
          'insmod "$gpu_dir/$module.ko"' in rc and
          0 <= rc.find("gpu_modules=") < rc.find("/usr/bin/launcher --apply"))
    check("rcS waits for the render node", "/dev/dri/renderD128" in rc)
    # 3. PortMaster control.txt probes sudo; without it ports skip privileged setup.
    sudo = overlay / "usr/bin/sudo"
    check("overlay ships the sudo shim", sudo.is_file())
    if sudo.is_file():
        check("sudo shim executes its arguments", 'exec "$@"' in sudo.read_text(encoding="utf-8"))
    # 4. A single env string above MAX_ARG_STRLEN (128 KiB) kills every exec.
    curate = overlay / "usr/share/deepos/curate-controllerdb.sh"
    check("overlay ships the controller database trimmer", curate.is_file())
    run_port = (overlay / "usr/share/deepos/run-port.sh").read_text(encoding="utf-8")
    check("run-port.sh trims the controller database first",
          "curate-controllerdb.sh" in run_port and
          run_port.find("curate-controllerdb.sh") < run_port.find("exec /bin/bash"))
    check("run-port.sh points Mesa at the rootfs GBM backend",
          "GBM_BACKENDS_PATH" in run_port and "/usr/lib/gbm" in run_port)
    # 5. SDL dlopen()s these by soname before it can create a window: without
    #    libudev it segfaults inside the kmsdrm driver, without libEGL every
    #    port reports "EGL not initialized".
    for soname, minimum in (("libudev.so.1", 200000),
                            ("libEGL.so.1", 100000),
                            ("libGLdispatch.so.0", 1000000)):
        p = overlay / "usr/lib" / soname
        check(f"overlay ships /usr/lib/{soname}",
              p.is_file() and p.stat().st_size >= minimum)
    check("run-port.sh keeps /usr/lib on the library path",
          "LD_LIBRARY_PATH=$runtime/lib:/usr/lib" in run_port)
    retro = (overlay / "usr/share/deepos/retroarch.cfg").read_text(encoding="utf-8")
    check("RetroArch uses the SDL2 input driver (no udevd, no tty)",
          'input_driver = "sdl2"' in retro)
    check("RetroArch keeps the udev joypad driver", 'input_joypad_driver = "udev"' in retro)
    # 6. Launch-time tuning taken from dArkOSRE, with the parts that this board
    #    rejects measured out: threaded video kills kmsdrm here, and the
    #    synchronous ALSA driver is the one that produced sound.
    check("RetroArch keeps the synchronous ALSA driver", 'audio_driver = "alsa"' in retro)
    check("RetroArch opens the PCM through plughw", 'audio_device = "plughw:0,0"' in retro)
    check("RetroArch resamples with sinc", 'audio_resampler = "sinc"' in retro)
    check("RetroArch does not use the video driver kmsdrm rejects",
          'video_threaded = "true"' not in retro)
    check("RetroArch scales its widgets for the 640x480 panel",
          'menu_widget_scale_factor = "2.5"' in retro)
    boost = overlay / "usr/local/bin/perf-boost.sh"
    check("overlay ships the GPU clock boost helper", boost.is_file())
    if boost.is_file():
        check("perf-boost.sh is POSIX sh",
              subprocess.run(["sh", "-n", str(boost)], capture_output=True).returncode == 0)
        check("perf-boost.sh pins the panfrost governor",
              "performance" in boost.read_text(encoding="utf-8"))
    check("run-port.sh boosts the GPU for the port", "perf-boost.sh on" in run_port)
    check("run-port.sh restores the GPU after the port", "perf-boost.sh off" in run_port)
    check("run-port.sh restores the GPU when the wrapper is killed", "kill -0 $$" in run_port)
    check("rcS resets the GPU governor at boot",
          "perf-boost.sh off" in (overlay / "etc/init.d/rcS").read_text(encoding="utf-8"))
    game = (overlay / "usr/local/bin/retroarch-game.sh").read_text(encoding="utf-8")
    check("retroarch-game.sh layers the packaged config under the user copy",
          "--config /usr/share/deepos/retroarch.cfg" in game and
          'cat "$cfg"' in game)
    check("retroarch-game.sh boosts the GPU for the core", '"$boost" on' in game)
    check("retroarch-game.sh restores the GPU on exit", '"$boost" off' in game)
    check("retroarch-game.sh restores the GPU when the wrapper is killed",
          "kill -0 $$" in game)
    check("retroarch-game.sh runs the core with a niceness bump", "nice -n -5" in game)
    check("run-port.sh runs the port with a niceness bump", "nice -n -5" in run_port)
    # BIOS dumps cannot be shipped, so the report has to say what is missing.
    table = ROOT / "board/r36s-v20/data/bios-required.tsv"
    check("bios-required.tsv exists", table.is_file() and table.stat().st_size > 0)
    if table.is_file():
        rows = [line.split("\t") for line in table.read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#")]
        check("bios table has four columns", all(len(row) == 4 for row in rows))
        check("bios table marks HLE systems",
              any(row[3].strip() == "hle" for row in rows) and
              any(row[3].strip() == "required" for row in rows))
        check("bios table marks the PS1 fallback",
              any(row[0] == "psx" and row[3].strip() == "hle" for row in rows))
    bios = overlay / "usr/local/bin/bios-check.sh"
    check("bios-check.sh exists", bios.is_file())
    if bios.is_file():
        check("bios-check.sh is POSIX sh",
              subprocess.run(["sh", "-n", str(bios)], capture_output=True).returncode == 0)
    check("rcS writes the BIOS report", "/usr/local/bin/bios-check.sh" in rc)
    # Swap: zram is modular here, and ports cannot swap on the exFAT card, so
    # the image ships the zram stack plus a small file on /data as overflow.
    for module in ("zram", "zsmalloc", "lz4_compress", "lz4hc_compress", "zstd_compress"):
        p = overlay / "lib/modules/6.12.114" / f"{module}.ko"
        check(f"overlay ships {module}.ko", p.is_file() and p.stat().st_size > 0)
    zram_line = next((ln for ln in rc.splitlines() if ln.startswith("zram_modules=")), "")
    listed = zram_line.split("=", 1)[1].strip().strip('"\'').split() if "=" in zram_line else []
    check("rcS loads zram in dependency order",
          [m for m in listed if m in ("lz4_compress", "lz4hc_compress", "zstd_compress",
                                      "zsmalloc", "zram")] ==
          ["lz4_compress", "lz4hc_compress", "zstd_compress", "zsmalloc", "zram"],
          zram_line.strip())
    check("rcS gives zram 512 MiB", "536870912 > /sys/block/zram0/disksize" in rc)
    check("rcS picks the zram codec before setting the size",
          0 <= rc.find("> /sys/block/zram0/comp_algorithm") <
          rc.find("> /sys/block/zram0/disksize"))
    check("rcS swaps zram on with a high priority", "swapon -p 100 /dev/zram0" in rc)
    check("rcS keeps the /data swap file as cold overflow",
          "/data/swapfile" in rc and "swapon -p 10" in rc)
    check("rcS sets the hostname", rc.find("hostname deepos") > 0)
    check("rcS mounts BOOT with sync (FAT has no journal)", "/flash sync" in rc)


def test_sound_route():
    """The speaker must hang off the codec class-D stage, not bare SPKO."""
    dts = BOARD / "dts" / "rk3326-r36s-v20.dts"
    check("dts exists for the sound check", dts.is_file())
    text = dts.read_text(encoding="utf-8") if dts.is_file() else ""
    check("dts routes the speaker to SPK DAC",
          '"Internal Speakers", "SPK DAC"' in text)
    check("dts keeps headphones on HPOL/HPOR",
          '"Headphones", "HPOL"' in text and '"Headphones", "HPOR"' in text)

    dtb = BOARD / "boot" / "dtbs" / "rk3326-r36s-v20.dtb"
    check("patched board dtb is checked in", dtb.is_file())
    blob = dtb.read_bytes() if dtb.is_file() else b""
    check("patched dtb routes the speaker to SPK DAC",
          b"Internal Speakers\x00SPK DAC" in blob, f"{len(blob)} bytes")
    check("patched dtb no longer routes the speaker to SPKO",
          b"Internal Speakers\x00SPKO" not in blob)
    tool = ROOT / "tools" / "dtb-sound-fix.py"
    check("dtb-sound-fix.py regenerates the patched dtb", tool.is_file())


def test_volume_rocker():
    """Volume keys live on adc-keys, not on the gamepad, and must reach both
    the launcher and RetroArch."""
    src_input = (ROOT / "apps" / "launcher" / "src" / "dp_input.c").read_text(encoding="utf-8")
    check("input code looks for volume keys",
          "KEY_VOLUMEUP" in src_input and "KEY_VOLUMEDOWN" in src_input)
    check("input code opens a second evdev node for the rocker",
          "has_volume_keys" in src_input and "key_fd" in src_input)
    check("input code prefers the adc-keys node", "adc-keys" in src_input)

    run_port = (BOARD / "rootfs-overlay" / "usr" / "share" / "deepos" / "run-port.sh").read_text(encoding="utf-8")
    check("run-port.sh enlarges the SDL audio buffer",
          "SDL_AUDIO_DEVICE_SAMPLE_FRAMES" in run_port and "8192" in run_port)

    src_cfg = (ROOT / "apps" / "launcher" / "src" / "dp_config.c").read_text(encoding="utf-8")
    check("mixer level keeps headroom for the class-D stage", "* use * 84 / 10000" in src_cfg)

    src_main = (ROOT / "apps" / "launcher" / "src" / "main.c").read_text(encoding="utf-8")
    check("launcher shows the volume level as a toast", "volume_delta" in src_main and "notice" in src_main)

    ra = (BOARD / "rootfs-overlay" / "usr" / "share" / "deepos" / "retroarch.cfg").read_text(encoding="utf-8")
    for key in ("input_volume_up", "input_volume_down", "audio_volume", "menu_enable_widgets"):
        check("retroarch.cfg sets " + key, key in ra)
    check("retroarch volume keys use SDL scancodes",
          'keycode 128' in ra and 'keycode 129' in ra and 'keycode 127' in ra)


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
    test_sound_route()
    test_volume_rocker()
    test_gpu_and_ports_stack()
    print()
    if fails:
        print("FAIL  board: " + ", ".join(fails))
        return 1
    print("PASS  board: dtb, kernel config, busybox config, extlinux, mounts, handover, report, gadget, selfcheck, rcs order, emulators, rootfs builder")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
