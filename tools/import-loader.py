#!/usr/bin/env python3
"""Copy a known-good Rockchip boot chain into a DEEPoS image.

The BootROM/DDR stage is the most board-specific part of the boot and the only
one we cannot test on the host. When a hand-built `idbloader.img` refuses to
start the console (black screen, no backlight) we borrow the chain from an image
that is known to boot on this exact board: bytes 32 KiB..16 MiB hold the
idbloader (DDR init + SPL) and U-Boot proper, and everything from 16 MiB on is
our own GPT.

  python tools/import-loader.py --image build/deepos.img --from-images ../images/ArchR-clone.img.gz

The donor may be a raw image or a gzip stream; only the first 16 MiB are read.
"""
import argparse
import gzip
import pathlib
import sys

START = 32 * 1024
END = 16 * 1024 * 1024


def read_donor(source, size):
    path = pathlib.Path(source)
    data = bytearray()
    opener = gzip.open if path.suffix.endswith(".gz") else open
    with opener(path, "rb") as handle:
        while len(data) < size:
            chunk = handle.read(min(1 << 20, size - len(data)))
            if not chunk:
                break
            data.extend(chunk)
    return bytes(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Import a Rockchip boot chain into an image")
    parser.add_argument("--image", required=True)
    parser.add_argument("--from-images", required=True, dest="donor")
    parser.add_argument("--start", default=START, type=int)
    parser.add_argument("--end", default=END, type=int)
    args = parser.parse_args(argv)

    size = args.end - args.start
    blob = read_donor(args.donor, args.end)
    if len(blob) < args.end:
        raise SystemExit(f"import-loader: donor is shorter than {args.end} bytes")
    region = blob[args.start:args.end]
    if region.count(b"\x00") == len(region):
        raise SystemExit("import-loader: donor loader area is empty")

    image = pathlib.Path(args.image)
    with image.open("r+b") as handle:
        handle.seek(args.start)
        handle.write(region)
        handle.flush()
    print(f"import-loader: {size // 1024} KiB from {args.donor} -> {args.image} at {args.start}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
