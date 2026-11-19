"""Check the display pipeline used by the R36S-V20 boot profile."""

import re
import subprocess

PANEL = "/dsi@ff450000/panel@0"
ARCHR_COMPATIBLE = "gameconsole,eeclone"


def get_string(dtb, node, prop):
    result = subprocess.run(
        ["fdtget", "-t", "s", str(dtb), node, prop],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def display_checks(dtb, kernel):
    board = get_string(dtb, "/", "compatible").split()
    yield (bool({"deepos,r36s-v20", ARCHR_COMPATIBLE}.intersection(board)),
           "dtb carries compatible deepos,r36s-v20 or gameconsole,eeclone")
    for name, node in (("VOP", "/vop@ff460000"), ("DSI", "/dsi@ff450000"),
                       ("subsystem", "/display-subsystem")):
        enabled = get_string(dtb, node, "status") in ("okay", "ok")
        yield enabled, f"display {name} is enabled"
    compatibles = get_string(dtb, PANEL, "compatible").split()
    image = kernel.read_bytes() if kernel.is_file() else b""
    yield (any(value.encode() + b"\0" in image for value in compatibles),
           "kernel supports the DTB panel compatible")
    if ARCHR_COMPATIBLE in board:
        description = get_string(dtb, PANEL, "panel_description")
        modes = re.findall(
            r"\bM clock=\d+ horizontal=(\d+),\d+,\d+,\d+ "
            r"vertical=(\d+),\d+,\d+,\d+ default=1(?=\s|$)", description)
        yield modes == [("640", "480")], "Arch-R V20 panel defaults to 640x480"
