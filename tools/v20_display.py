"""Check the display pipeline used by the R36S-V20 boot profile."""

import subprocess

PANEL = "/dsi@ff450000/panel@0"


def get_string(dtb, node, prop):
    result = subprocess.run(
        ["fdtget", "-t", "s", str(dtb), node, prop],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def display_checks(dtb, kernel):
    board = get_string(dtb, "/", "compatible").split()
    yield (bool({"deepos,r36s-v20", "gameconsole,eeclone"}.intersection(board)),
           "dtb carries compatible deepos,r36s-v20 or gameconsole,eeclone")
    for name, node in (("VOP", "/vop@ff460000"), ("DSI", "/dsi@ff450000"),
                       ("subsystem", "/display-subsystem")):
        enabled = get_string(dtb, node, "status") in ("okay", "ok")
        yield enabled, f"display {name} is enabled"
    compatibles = get_string(dtb, PANEL, "compatible").split()
    image = kernel.read_bytes() if kernel.is_file() else b""
    yield (any(value.encode() + b"\0" in image for value in compatibles),
           "kernel supports the DTB panel compatible")
