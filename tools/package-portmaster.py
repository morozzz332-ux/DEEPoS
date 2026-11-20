#!/usr/bin/env python3
"""Build the opt-in PortMaster runtime from upstream and a local Arch-R donor."""
import argparse
import hashlib
from pathlib import Path
import runpy
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

PORTMASTER_SHA256 = "d96a921ed3110f3c1b56b1f5b88d34539241723bd2fb003f29edbce5402a4fef"
PYTHON = "python3.13"


def install_python(runtime):
    runtime.elf(f"/usr/bin/{PYTHON}", "bin/python3")
    runtime.debugfs(f'rdump "/usr/lib/{PYTHON}" "{runtime.directory / "lib"}"')
    stdlib = runtime.directory / "lib" / PYTHON
    if not (stdlib / "encodings").is_dir():
        raise ValueError("donor Python standard library is missing")
    for name in ("site-packages", "test", "idlelib", "tkinter", "ensurepip", "turtledemo"):
        path = stdlib / name
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
    for path in stdlib.rglob("*"):
        if path.is_symlink() and path.readlink().is_absolute():
            path.unlink()
    extensions = stdlib / "lib-dynload"
    for path in sorted(extensions.glob("*.so")):
        if path.name.startswith(("_tkinter.", "_test", "_ctypes_test.")):
            path.unlink()
            continue
        runtime.elf(f"/usr/lib/{PYTHON}/lib-dynload/{path.name}",
                    f"lib/{PYTHON}/lib-dynload/{path.name}")


def build(donor, upstream, out, extracted):
    with upstream.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != PORTMASTER_SHA256:
            raise ValueError("unexpected PortMaster ZIP. Use upstream release 2026.11.17-0700")
    importer = runpy.run_path(str(Path(__file__).with_name("import-retroarch.py")))
    with tempfile.TemporaryDirectory(prefix="deepos-portmaster-") as work:
        base = Path(work)
        if extracted is None:
            extracted = base / "archr.ext4"
            importer["extract_ext4"](donor, extracted)
        staged = base / "portmaster"
        runtime = importer["Runtime"](extracted, staged / "runtime")
        runtime.elf("/usr/bin/bash", "bin/bash")
        runtime.elf("/usr/bin/getconf", "bin/getconf")
        install_python(runtime)
        for library in ("ld-linux-aarch64.so.1", "libSDL2-2.0.so.0",
                        "libSDL2_image-2.0.so.0", "libSDL2_ttf-2.0.so.0",
                        "libSDL2_mixer-2.0.so.0", "libEGL_mesa.so.0", "libGLESv2.so.2"):
            runtime.library(library)
        runtime.elf("/usr/lib/dri/panfrost_dri.so", "lib/dri/panfrost_dri.so")
        (runtime.directory / "lib/dri/rockchip_dri.so").symlink_to("panfrost_dri.so")
        (runtime.directory / "lib/dri/swrast_dri.so").symlink_to("panfrost_dri.so")
        runtime.dump("/usr/share/glvnd/egl_vendor.d/50_mesa.json", runtime.directory / "egl/50_mesa.json")
        shutil.copyfile("/etc/ssl/certs/ca-certificates.crt", runtime.directory / "ca-bundle.crt")
        runtime.debugfs(f'rdump /usr/share/alsa "{runtime.directory}"')
        for path in (runtime.directory / "alsa").rglob("*"):
            if path.is_symlink() and path.readlink().is_absolute():
                path.unlink()
        with zipfile.ZipFile(upstream) as archive:
            archive.extractall(staged)
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                file = staged / entry.filename
                with file.open("rb") as source:
                    magic = source.read(4)
                if entry.external_attr >> 16 & 0o111 or magic == b"\x7fELF" or magic[:2] == b"#!":
                    file.chmod(0o755)
        control = staged / "PortMaster"
        for name in ("pugwash", "harbourmaster", "gptokeyb", "gptokeyb2", "portmsg.aarch64",
                     "sdl_resolution.aarch64", "7zzs.aarch64"):
            (control / name).chmod(0o755)
        # The upstream Python CLI and GUI use the same bundled pylibs tree.
        out.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(out, "w:gz", compresslevel=4, format=tarfile.PAX_FORMAT) as archive:
            archive.add(staged, arcname="portmaster")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    donor = parser.add_mutually_exclusive_group(required=True)
    donor.add_argument("--donor", type=Path, help="local Arch-R Clone image (.img or .img.gz)")
    donor.add_argument("--donor-ext4", type=Path, help="already extracted read-only donor partition")
    parser.add_argument("--upstream", required=True, type=Path, help="official PortMaster.zip")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        build(args.donor, args.upstream, args.out, args.donor_ext4)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"package-portmaster: {exc}\n")


if __name__ == "__main__":
    main()
