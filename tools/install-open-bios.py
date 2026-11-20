#!/usr/bin/env python3
"""Copy the DEEPoS open BIOS set to a ROMS volume."""
import argparse
import hashlib
from pathlib import Path, PurePosixPath

BIOS = Path(__file__).resolve().parents[1] / "bios"


def sha256(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def install(roms, package=BIOS):
    if not roms.is_dir():
        raise ValueError(f"ROMS directory does not exist: {roms}")
    sources = {}
    manifest = (package / "manifest.tsv").read_text(encoding="utf-8").splitlines()
    for line in manifest[1:]:
        algorithm, expected, name = line.split("\t", 2)
        if algorithm != "sha256":
            raise ValueError(f"unsupported BIOS checksum algorithm: {algorithm}")
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
            raise ValueError(f"invalid BIOS path: {name}")
        source = package / "files" / path
        if sha256(source) != expected:
            raise ValueError(f"BIOS checksum mismatch: {name}")
        sources[path] = source

    installed = current = kept = 0
    destination = roms / "bios"
    for path, source in sources.items():
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            file = target.open("xb")
        except FileExistsError:
            if target.is_file() and sha256(target) == sha256(source):
                current += 1
            else:
                print(f"Preserved existing {path}")
                kept += 1
        else:
            try:
                with file:
                    file.write(source.read_bytes())
            except OSError:
                target.unlink()
                raise
            installed += 1
    return installed, current, kept


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roms", type=Path, required=True, help="root of the ROMS volume")
    args = parser.parse_args()
    try:
        installed, current, kept = install(args.roms)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"install-open-bios: {exc}\n")
    print(f"Installed {installed}, already present {current}, existing files preserved {kept}")


if __name__ == "__main__":
    main()
