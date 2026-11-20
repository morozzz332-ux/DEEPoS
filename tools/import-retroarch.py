#!/usr/bin/env python3
"""Import the ARM64 RetroArch runtime and selected cores from an Arch-R Clone image."""

import argparse
import gzip
import posixpath
import re
import struct
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from elftools.elf.elffile import ELFFile


def extract_ext4(image, destination):
    opener = gzip.open if image.suffix == ".gz" else open
    with opener(image, "rb") as source:
        mbr = source.read(512)
        if len(mbr) != 512 or mbr[510:] != b"\x55\xaa" or mbr[466] not in (0x83, 0xDA):
            raise ValueError("expected the Arch-R Clone MBR and second Linux partition")
        first, sectors = struct.unpack_from("<II", mbr, 470)
        if first < 32768 or not 8 <= sectors <= 32 * 1024 * 1024:
            raise ValueError("unexpected Arch-R root partition geometry")
        source.seek(first * 512)
        header = source.read(4096)
        if header[1080:1082] != b"\x53\xef":
            raise ValueError("the second Arch-R partition is not ext4")
        with destination.open("wb") as out:
            out.write(header)
            remaining = sectors * 512 - len(header)
            while remaining:
                chunk = source.read(min(remaining, 4 * 1024 * 1024))
                if not chunk:
                    raise ValueError("truncated Arch-R root partition")
                if any(chunk[::4096]) or chunk.count(0) != len(chunk):
                    out.write(chunk)
                else:
                    out.seek(len(chunk), 1)
                remaining -= len(chunk)
            out.truncate(sectors * 512)


class Runtime:
    def __init__(self, disk, directory):
        self.disk = disk
        self.directory = directory
        self.libraries = set()

    def debugfs(self, command):
        result = subprocess.run(["debugfs", "-R", command, self.disk], check=True,
                                capture_output=True, text=True)
        return result.stdout

    def dump(self, source, target):
        for _ in range(12):
            stat = self.debugfs(f'stat "{source}"')
            match = re.search(r'Fast link dest: "([^"]+)"', stat)
            if not match:
                break
            source = posixpath.normpath(posixpath.join(posixpath.dirname(source), match[1]))
        else:
            raise ValueError(f"too many symlinks for {source}")
        if "Type: regular" not in stat:
            raise ValueError(f"missing regular file in Arch-R: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        self.debugfs(f'dump "{source}" "{target}"')
        if not target.is_file():
            raise ValueError(f"could not extract {source}")

    def elf(self, source, relative):
        target = self.directory / relative
        self.dump(source, target)
        target.chmod(0o755)
        with target.open("rb") as file:
            elf = ELFFile(file)
            if elf.elfclass != 64 or elf["e_machine"] != "EM_AARCH64":
                raise ValueError(f"expected an AArch64 ELF file: {source}")
            dynamic = elf.get_section_by_name(".dynamic")
            dependencies = ([tag.needed for tag in dynamic.iter_tags("DT_NEEDED")]
                            if dynamic else [])
        for name in dependencies:
            self.library(name)

    def library(self, name):
        if name in self.libraries:
            return
        if not re.fullmatch(r"[\w.+-]+", name):
            raise ValueError(f"invalid library name: {name}")
        self.libraries.add(name)
        for directory in ("/usr/lib", "/usr/lib/pulseaudio"):
            path = f"{directory}/{name}"
            if "Inode:" in self.debugfs(f'stat "{path}"'):
                self.elf(path, f"lib/{name}")
                return
        raise ValueError(f"missing AArch64 dependency in Arch-R: {name}")

    def import_cores(self, cores):
        self.elf("/usr/bin/retroarch", "retroarch")
        for name in ("ld-linux-aarch64.so.1", "libEGL_mesa.so.0", "libGLESv2.so.2"):
            self.library(name)
        self.elf("/usr/lib/dri/panfrost_dri.so", "lib/dri/panfrost_dri.so")
        (self.directory / "lib/dri/rockchip_dri.so").symlink_to("panfrost_dri.so")
        self.dump("/usr/share/glvnd/egl_vendor.d/50_mesa.json",
                  self.directory / "egl/50_mesa.json")
        self.dump("/usr/share/libretro/autoconfig/r36s_Gamepad.cfg",
                  self.directory / "autoconfig/r36s_Gamepad.cfg")
        alsa = self.directory / "alsa"
        self.debugfs(f'rdump /usr/share/alsa {self.directory}')
        if not (alsa / "alsa.conf").is_file():
            raise ValueError("ALSA configuration missing in Arch-R")
        for link in alsa.rglob("*"):
            if link.is_symlink() and link.readlink().is_absolute():
                link.unlink()
        for core in cores:
            name = core + "_libretro.so"
            self.elf(f"/usr/lib/libretro/{name}", f"cores/{name}")

    def import_catalog(self, restricted):
        catalog_file = self.directory.parent / "systems.cfg"
        self.dump("/usr/share/archr/systems.cfg", catalog_file)
        listing = self.debugfs("ls -p /usr/lib/libretro")
        names = set(re.findall(r"/([a-zA-Z0-9_]+)_libretro\.so/", listing))
        block_size = int(re.search(r"(?m)^Block size:\s*(\d+)", self.debugfs("stats"))[1])
        available = set()
        with self.disk.open("rb") as disk:
            for name in sorted(names):
                if restricted and name not in restricted:
                    continue
                source = f"/usr/lib/libretro/{name}_libretro.so"
                block = self.debugfs(f"bmap {source} 0").strip()
                if not block.isdigit() or block == "0":
                    continue
                disk.seek(int(block) * block_size)
                header = disk.read(20)
                if header[:6] == b"\x7fELF\x02\x01" and header[18:20] == b"\xb7\0":
                    available.add(name)
        entries, extensions, missing = [], [], []
        for system in ET.parse(catalog_file).findall("system"):
            system_id = system.findtext("name", "").strip()
            if not re.fullmatch(r"[a-z0-9_-]+", system_id):
                continue
            cores = system.findall('emulators/emulator[@name="retroarch"]/cores/core')
            cores.sort(key=lambda core: core.get("default") != "true")
            choices = [core.text for core in cores if core.text in available]
            if not choices:
                missing.append(system_id)
                continue
            entries.append((system_id, choices[0]))
            suffixes = system.findtext("extension", "").lower().split()
            suffixes = sorted({s for s in suffixes if re.fullmatch(r"\.[a-z0-9_+-]+", s)})
            extensions.append(f"{system_id}\t{' '.join(suffixes)}\n")
        self.directory.mkdir()
        (self.directory / "systems.toml").write_text("".join(
            f'{system_id} = "/usr/local/bin/retroarch-game.sh {core} %ROM%"\n'
            for system_id, core in entries), encoding="utf-8")
        (self.directory / "extensions.tsv").write_text("".join(extensions), encoding="utf-8")
        (self.directory / "unmapped.txt").write_text("\n".join(missing) + "\n", encoding="utf-8")
        return {core for _, core in entries}, len(entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--donor", type=Path, help="Arch-R Clone .img or .img.gz")
    source.add_argument("--root-ext4", type=Path, help="already extracted Arch-R root partition")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=Path(__file__).resolve().parents[1] /
                        "board/r36s-v20/data/emulators.toml")
    parser.add_argument("--core", action="append", help="restrict import to these core IDs")
    args = parser.parse_args()
    try:
        cores = sorted(set(args.core or re.findall(r"retroarch-game\.sh ([a-zA-Z0-9_]+) %ROM%",
                                                   args.registry.read_text(encoding="utf-8"))))
        if not cores or any(not re.fullmatch(r"[a-zA-Z0-9_]+", core) for core in cores):
            raise ValueError("specify valid libretro core IDs")
        with tempfile.TemporaryDirectory(prefix="deepos-emu-") as name:
            tmp = Path(name)
            disk = args.root_ext4 or (tmp / "donor.ext4")
            if args.donor:
                extract_ext4(args.donor, disk)
            runtime = Runtime(disk, tmp / "emus")
            catalog_cores, systems = runtime.import_catalog(set(args.core or []))
            cores = sorted(set(cores) | catalog_cores)
            runtime.import_cores(cores)
            with tarfile.open(args.out, "x:gz", compresslevel=3) as archive:
                archive.add(runtime.directory, arcname="emus")
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"import-retroarch: {exc}\n")
    print(f"{args.out}: {systems} Arch-R system entries, {len(cores)} ARM64 cores, "
          f"{len(runtime.libraries)} libraries")


if __name__ == "__main__":
    main()
