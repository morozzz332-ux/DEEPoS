#!/usr/bin/env python3
"""Package the other ARM64 RetroArch cores and their system-to-core catalogue."""
import argparse
import hashlib
from pathlib import Path
import re
import runpy
import tarfile
import tempfile
import tomllib
import xml.etree.ElementTree as ET
import zipfile

EMUSCV_SHA256 = "76083b0e798bb83d0cb7ad1ecb46ec164068205b1de5088976fa96b14303eb61"


def build(donor, donor_ext4, base, out, emuscv):
    importer = runpy.run_path(str(Path(__file__).with_name("import-retroarch.py")))
    with tarfile.open(base) as original:
        already_installed = {
            match[1] for name in original.getnames()
            if (match := re.fullmatch(r"emus/cores/([a-zA-Z0-9_-]+)_libretro\.so", name))
        }
    if not already_installed:
        raise ValueError("base archive contains no ARM64 cores")
    with tempfile.TemporaryDirectory(prefix="deepos-cores-") as folder:
        work = Path(folder)
        if donor_ext4 is None:
            donor_ext4 = work / "archr.ext4"
            importer["extract_ext4"](donor, donor_ext4)
        runtime = importer["Runtime"](donor_ext4, work / "extra-emulators")
        listing = runtime.debugfs("ls -p /usr/lib/libretro")
        block_size = int(re.search(r"(?m)^Block size:\s*(\d+)", runtime.debugfs("stats"))[1])
        names = set(re.findall(r"/([a-zA-Z0-9_-]+)_libretro\.so/", listing))
        installed = set(already_installed)
        with donor_ext4.open("rb") as image:
            for core in sorted(names - already_installed):
                filename = core + "_libretro.so"
                source = f"/usr/lib/libretro/{filename}"
                block = runtime.debugfs(f"bmap {source} 0").strip()
                if not block.isdigit() or block == "0":
                    print(f"Skip {core}: no native program")
                    continue
                image.seek(int(block) * block_size)
                header = image.read(20)
                if header[:6] != b"\x7fELF\x02\x01" or header[18:20] != b"\xb7\0":
                    print(f"Skip {core}: not AArch64")
                    continue
                runtime.elf(source, "cores/" + filename)
                installed.add(core)

        catalog = work / "systems.cfg"
        runtime.dump("/usr/share/archr/systems.cfg", catalog)
        usable = installed - {"flycast2021", "emuscv"}
        if emuscv:
            with emuscv.open("rb") as file:
                if hashlib.file_digest(file, "sha256").hexdigest() != EMUSCV_SHA256:
                    raise ValueError("unexpected EmuSCV buildbot archive")
            with zipfile.ZipFile(emuscv) as archive:
                replacement = archive.read("emuscv_libretro.so")
            target = runtime.directory / "cores/emuscv_libretro.so"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(replacement)
            usable.add("emuscv")
        choices = {}
        for system in ET.parse(catalog).findall("system"):
            key = system.findtext("name", "").strip()
            if not re.fullmatch(r"[a-z0-9_-]{1,23}", key):
                continue
            cores = system.findall('emulators/emulator[@name="retroarch"]/cores/core')
            cores.sort(key=lambda core: core.get("default") != "true")
            supported = list(dict.fromkeys(core.text for core in cores if core.text in usable))
            if supported:
                choices[key] = supported
        defaults = Path(__file__).resolve().parents[1] / "board/r36s-v20/data/emulators.toml"
        for alias, command in tomllib.loads(defaults.read_text(encoding="utf-8")).items():
            match = re.fullmatch(r"/usr/local/bin/retroarch-game\.sh ([\w-]+) %ROM%", command)
            if alias not in choices and match and match[1] in usable:
                choices[alias] = next((cores for cores in choices.values() if cores[0] == match[1]),
                                      [match[1]])
        (runtime.directory / "cores.tsv").write_text("".join(
            f"{key}\t{' '.join(cores)}\n" for key, cores in choices.items()), encoding="utf-8")
        (runtime.directory / "systems.toml").write_text("".join(
            f'{key} = "/usr/local/bin/retroarch-game.sh {cores[0]} %ROM%"\n'
            for key, cores in choices.items()), encoding="utf-8")
        out.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(out, "w:gz", compresslevel=4) as archive:
            archive.add(runtime.directory, arcname="extra-emulators")
        print(f"{len(installed)} ARM64 cores ({len(installed - already_installed)} additional); "
              f"{len(usable)} eligible for the catalogue, {len(choices)} system entries")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--donor", type=Path)
    source.add_argument("--donor-ext4", type=Path)
    parser.add_argument("--base-runtime", required=True, type=Path)
    parser.add_argument("--emuscv", type=Path, help="verified libretro buildbot EmuSCV ZIP")
    parser.add_argument("--out", required=True, type=Path)
    options = parser.parse_args()
    build(options.donor, options.donor_ext4, options.base_runtime, options.out, options.emuscv)


if __name__ == "__main__":
    main()
