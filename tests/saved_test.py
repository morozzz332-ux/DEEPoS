#!/usr/bin/env python3
"""Host tests for apps/saved: atomic save-state store.

Runs against the real binary in a throwaway directory. No device needed.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "apps", "saved", "saved")

failures = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        failures.append(name)


def run(args, expect=0):
    proc = subprocess.run([BIN] + args, capture_output=True, text=True)
    if proc.returncode != expect:
        failures.append(f"exit {proc.returncode} != {expect}: {' '.join(args)} :: {proc.stderr.strip()}")
    return proc


def write_file(path, data):
    with open(path, "wb") as handle:
        handle.write(data)


def slot_path(data, system, rom, slot, ext="state"):
    return os.path.join(data, "saves", system, rom, f"slot{slot}.{ext}")


def main():
    if not os.path.exists(BIN):
        print(f"FAIL: binary not built: {BIN}")
        return 1
    data = tempfile.mkdtemp(prefix="deepos-saved-")
    src = os.path.join(data, "src.bin")
    try:
        print("saved: put/get roundtrip")
        write_file(src, b"A" * 4096)
        run(["--data", data, "put", "--system", "md", "--rom", "sonic3", "--slot", "2", "--file", src])
        target = slot_path(data, "md", "sonic3", 2)
        check("state file exists", os.path.exists(target))
        check("state size", os.path.getsize(target) == 4096)
        meta = json.load(open(slot_path(data, "md", "sonic3", 2, "json")))
        check("meta slot", meta["slot"] == 2)
        check("meta size", meta["size"] == 4096)
        got = run(["--data", data, "get", "--system", "md", "--rom", "sonic3", "--slot", "2"])
        check("get prints path", got.stdout.strip() == target, got.stdout.strip())

        print("saved: last / list")
        write_file(src, b"B" * 1024)
        run(["--data", data, "put", "--system", "md", "--rom", "sonic3", "--slot", "0", "--file", src])
        last = run(["--data", data, "last", "--system", "md", "--rom", "sonic3"])
        check("last is newest slot", last.stdout.strip() == "0", last.stdout.strip())
        listing = run(["--data", data, "list", "--system", "md", "--rom", "sonic3"])
        rows = [line.split() for line in listing.stdout.strip().splitlines()]
        check("list has two slots", len(rows) == 2, str(rows))
        check("list sizes", sorted(int(r[1]) for r in rows) == [1024, 4096])

        print("saved: overwrite keeps single file")
        write_file(src, b"C" * 2048)
        run(["--data", data, "put", "--system", "md", "--rom", "sonic3", "--slot", "2", "--file", src])
        check("overwrite size", os.path.getsize(target) == 2048)
        check("no tmp left", not os.path.exists(target + ".tmp"))

        print("saved: errors")
        run(["--data", data, "get", "--system", "md", "--rom", "sonic3", "--slot", "4"], expect=4)
        run(["--data", data, "last", "--system", "md", "--rom", "absent"], expect=4)
        run(["--data", data, "put", "--system", "md", "--rom", "sonic3", "--slot", "9", "--file", src], expect=3)
        run(["--data", data, "put", "--system", "md", "--rom", "sonic3", "--slot", "1"], expect=3)

        print("saved: crash recovery drops torn write, keeps committed slot")
        good = slot_path(data, "md", "sonic3", 3)
        write_file(good, b"G" * 512)
        torn = good + ".tmp"
        write_file(torn, b"T" * 512)
        journal = os.path.join(data, "saves", ".journal")
        os.makedirs(os.path.dirname(journal), exist_ok=True)
        with open(journal, "a", encoding="utf-8") as handle:
            handle.write(f"BEGIN {good}\n")
        recovered = run(["--data", data, "recover"])
        check("recover removed tmp", not os.path.exists(torn))
        check("recover kept committed file", os.path.getsize(good) == 512)
        check("recover reported one", "1" in recovered.stdout, recovered.stdout.strip())
        check("journal cleared", not os.path.exists(journal))

        print("saved: clean drops leftovers")
        write_file(good + ".tmp", b"X")
        write_file(slot_path(data, "md", "sonic3", 3, "json") + ".tmp", b"{}")
        run(["--data", data, "clean", "--system", "md", "--rom", "sonic3"])
        check("clean removed state tmp", not os.path.exists(good + ".tmp"))
        check("clean removed meta tmp", not os.path.exists(slot_path(data, "md", "sonic3", 3, "json") + ".tmp"))
        check("clean kept state", os.path.exists(good))
    finally:
        shutil.rmtree(data, ignore_errors=True)

    if failures:
        print(f"\nFAIL  saved: {len(failures)} problem(s)")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("\nPASS  saved: put/get, last, list, overwrite, errors, recover, clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
