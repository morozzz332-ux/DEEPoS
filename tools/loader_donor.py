"""Read the boot chain of a known-good Rockchip donor image."""

import gzip
import pathlib

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


def donor_region(source):
    blob = read_donor(source, END)
    if len(blob) < END:
        raise ValueError(f"donor is shorter than {END} bytes")
    region = blob[START:END]
    if not any(region):
        raise ValueError("donor loader area is empty")
    return region
