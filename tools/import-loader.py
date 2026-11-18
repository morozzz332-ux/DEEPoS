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
import pathlib

from loader_donor import START, END, donor_region


def main(argv=None):
    parser = argparse.ArgumentParser(description="Import a Rockchip boot chain into an image")
    parser.add_argument("--image", required=True)
    parser.add_argument("--from-images", required=True, dest="donor")
    parser.add_argument("--start", default=START, type=int)
    parser.add_argument("--end", default=END, type=int)
    args = parser.parse_args(argv)

    if not START <= args.start < args.end <= END:
        parser.error("donor range must stay within the Rockchip loader area")
    try:
        region = donor_region(args.donor)[args.start - START:args.end - START]
    except (OSError, ValueError) as exc:
        raise SystemExit(f"import-loader: {exc}") from exc
    size = len(region)

    image = pathlib.Path(args.image)
    if image.stat().st_size < args.end:
        raise SystemExit("import-loader: target image is shorter than the loader area")
    with image.open("r+b") as handle:
        handle.seek(args.start)
        handle.write(region)
        handle.flush()
    print(f"import-loader: {size // 1024} KiB from {args.donor} -> {args.image} at {args.start}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
