#!/usr/bin/env python3
"""Compare the board DTB against the stock DTB dumped from the device.

The stock dump (tests/fixtures/stock-rf3536k3ka.dtb) is the ground truth for
GPIO wiring and panel timings: if our hand-written DTS drops a button line or
typos a timing, this test catches it long before anybody powers the console.
"""
import argparse
import pathlib
import re
import subprocess
import sys
import tempfile

from board_test import BOARD, CPP

ROOT = pathlib.Path(__file__).resolve().parents[1]
OURS = ROOT / "build/kernel/rk3326-r36s-v20.dtb"
STOCK = ROOT / "tests/fixtures/stock-rf3536k3ka.dtb"
CONFIG = ROOT / "build/kernel/kernel.config"

failures = []


def check(cond, message):
    if cond:
        print(f"  ok   {message}")
    else:
        print(f"  FAIL {message}")
        failures.append(message)


def to_dts(path):
    out = subprocess.run(["dtc", "-I", "dtb", "-O", "dts", str(path)],
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"dtc failed for {path}: {out.stderr[:200]}")
    return out.stdout


def phandle_paths(text):
    """Map phandle value -> node path (dtc output nests nodes with braces)."""
    mapping = {}
    stack = []
    for line in text.splitlines():
        s = line.strip()
        node = re.match(r"^([A-Za-z0-9_@,.\-]+)\s*\{", s)
        if node:
            stack.append(node.group(1))
            continue
        if s.startswith("}"):
            if stack:
                stack.pop()
            continue
        ph = re.match(r"phandle\s*=\s*<0x([0-9a-f]+)>", s)
        if ph:
            mapping[int(ph.group(1), 16)] = "/".join(stack)
    return mapping


def gpio_key_pins(text, prop="key-gpios"):
    m = re.search(prop + r"\s*=\s*<([^>]*)>", text)
    if not m:
        return set()
    nums = [int(x, 16) if x.startswith("0x") else int(x) for x in m.group(1).split()]
    return {(nums[i], nums[i + 1]) for i in range(0, len(nums) - 2, 3)}


def labels_to_pins(text):
    """Collect the pin lines of every gpio-keys style child node."""
    pins = set()
    # Only the plain "gpios" property of a key node: "reset-gpios", "spk-con-gpio"
    # and friends must not leak into the key set.
    for m in re.finditer(r"(?<![\w-])gpios\s*=\s*<(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s+0x[0-9a-f]+>", text):
        pins.add((int(m.group(1), 16), int(m.group(2), 16)))
    return pins


def panel_props(text):
    panel = re.search(r"panel@0\s*\{(.*?)\n\t\t\};", text, re.S)
    body = panel.group(1) if panel else text
    props = {}
    for key in ("clock-frequency", "hactive", "vactive", "hfront-porch",
                "hback-porch", "hsync-len", "vfront-porch", "vback-porch",
                "vsync-len", "dsi,lanes", "dsi,flags"):
        m = re.search(re.escape(key) + r"\s*=\s*<0x([0-9a-f]+)>", body)
        if m:
            props[key] = int(m.group(1), 16)
    return props


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--built", action="store_true",
                        help="require and validate the built DTB and merged kernel config")
    args = parser.parse_args()
    stock = to_dts(STOCK)
    if args.built:
        ours = to_dts(OURS)
        cfg = CONFIG.read_text(encoding="utf-8")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            pre = pathlib.Path(tmp) / "board.dts"
            dtb = pathlib.Path(tmp) / "board.dtb"
            subprocess.run(CPP + [str(BOARD / "dts/rk3326-r36s-v20.dts"),
                                  "-o", str(pre)], check=True)
            subprocess.run(["dtc", "-I", "dts", "-O", "dtb", "-o", str(dtb),
                            str(pre)], check=True, capture_output=True)
            ours = to_dts(dtb)
        cfg = (BOARD / "linux.config").read_text(encoding="utf-8")
    stock_map = phandle_paths(stock)
    ours_map = phandle_paths(ours)

    def address_of(phandle, mapping):
        path = mapping.get(phandle, "")
        m = re.search(r"@([0-9a-f]{8})", path)
        return m.group(1) if m else None

    stock_keys = {(address_of(p, stock_map), pin) for p, pin in gpio_key_pins(stock)}
    ours_keys = {(address_of(p, ours_map), pin) for p, pin in labels_to_pins(ours)}
    stock_keys.discard((None, None))
    check(len(stock_keys) == 19, f"stock DTB declares 19 key lines (got {len(stock_keys)})")
    missing = sorted(stock_keys - ours_keys, key=str)
    extra = sorted(ours_keys - stock_keys, key=str)
    check(not missing, f"every stock key line is present (missing {missing})")
    check(not extra, f"no invented key lines (extra {extra})")

    sp = panel_props(stock)
    op = panel_props(ours)
    for key, value in sp.items():
        check(op.get(key) == value, f"panel {key} matches stock ({value})")
    check(op.get("dsi,lanes") == 4, "panel uses 4 DSI lanes")

    reset = re.search(r"reset-gpios\s*=\s*<0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)>", ours)
    check(reset is not None and int(reset.group(2), 16) == 15,
          "panel reset is GPIO3_B7 (active low)")

    model = re.search(r'model = "([^"]*)"', ours)
    compat = re.search(r'compatible = "([^"]*)"', ours)
    check(model is not None and "DEEPoS" in model.group(1), "DTB model names DEEPoS")
    check(compat is not None and "deepos,r36s-v20" in compat.group(1),
          "DTB compatible carries deepos,r36s-v20")

    required = {
        "CONFIG_DRM_PANEL_SITRONIX_ST7703": "panel driver",
        "CONFIG_DRM_ROCKCHIP": "rockchip DRM",
        "CONFIG_DRM_FBDEV_EMULATION": "fbdev emulation",
        "CONFIG_MFD_RK8XX": "PMIC core",
        "CONFIG_CHARGER_RK817": "battery gauge",
        "CONFIG_SND_SOC_RK817": "audio codec",
        "CONFIG_MMC_DW_ROCKCHIP": "sdmmc",
        "CONFIG_SQUASHFS_ZSTD": "rootfs compression",
        "CONFIG_EXFAT_FS": "rom partition",
        "CONFIG_USB_CONFIGFS_ACM": "usb console",
        "CONFIG_USB_CONFIGFS_NCM": "usb network",
        "CONFIG_KEYBOARD_GPIO": "buttons",
        "CONFIG_JOYSTICK_ADC": "sticks",
        "CONFIG_PWM_ROCKCHIP": "backlight",
        "CONFIG_KEYBOARD_ADC": "volume rocker",
    }
    for symbol, reason in required.items():
        line = next((l.strip() for l in cfg.splitlines() if l.startswith(symbol + "=")), "")
        check(line.endswith("=y"), f"{reason} built in ({symbol}=y)")

    print()
    if failures:
        print(f"FAIL  hardware: {len(failures)} check(s) failed")
        return 1
    print("PASS  hardware: DTB matches stock wiring, panel timings and kernel drivers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
