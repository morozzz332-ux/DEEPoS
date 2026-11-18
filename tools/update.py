#!/usr/bin/env python3
"""A/B boot bookkeeping for DEEPoS.

The root filesystem lives in two squashfs slots (SYS_A / SYS_B). A tiny state
file on the DATA partition records which slot should be booted next, how many
boot attempts the current slot already consumed and whether the last update
must be rolled back.

Rules (same idea as Android A/B, simplified):

* a freshly installed slot is booted with ``attempts = 0``;
* every boot increments ``attempts``; when it exceeds ``MAX_ATTEMPTS`` (3) the
  slot is considered broken and the state flips to the other slot with
  ``rollback = true``;
* userspace calls ``good`` once the launcher is up: attempts reset to 0 and the
  rollback flag clears.

Usage:
    update.py --state <dir> status
    update.py --state <dir> decide
    update.py --state <dir> begin
    update.py --state <dir> good
    update.py --state <dir> switch A|B
"""

import argparse
import json
import os
import pathlib
import sys
import tempfile

MAX_ATTEMPTS = 3
SLOTS = ("A", "B")


def state_path(state_dir):
    return pathlib.Path(state_dir) / "boot.json"


def default_state():
    return {"slot": "A", "attempts": 0, "rollback": False, "generation": 0}


def other(slot):
    if slot not in SLOTS:
        raise SystemExit(f"bad slot {slot!r}, expected A or B")
    return "B" if slot == "A" else "A"


def load(state_dir):
    p = state_path(state_dir)
    if not p.is_file():
        return default_state()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"corrupted boot state {p}: {exc}")
    st = default_state()
    st.update({k: data[k] for k in st if k in data})
    if st["slot"] not in SLOTS:
        st["slot"] = "A"
    return st


def save(state_dir, st):
    d = pathlib.Path(state_dir)
    d.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(d), prefix=".boot-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=2, sort_keys=True)
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, state_path(d))


def decide(st):
    """Slot the bootloader should use for the next boot."""
    return st["slot"]


def begin_boot(st, max_attempts=MAX_ATTEMPTS):
    """Account for one boot attempt; returns the state to persist."""
    st = dict(st)
    st["attempts"] = st.get("attempts", 0) + 1
    if st["attempts"] > max_attempts:
        st["slot"] = other(st["slot"])
        st["attempts"] = 0
        st["rollback"] = True
        st["generation"] = st.get("generation", 0) + 1
    return st


def mark_good(st):
    st = dict(st)
    st["attempts"] = 0
    st["rollback"] = False
    return st


def switch_slot(st, slot):
    if slot not in SLOTS:
        raise SystemExit(f"bad slot {slot!r}, expected A or B")
    st = dict(st)
    st["slot"] = slot
    st["attempts"] = 0
    st["rollback"] = False
    st["generation"] = st.get("generation", 0) + 1
    return st


def main(argv=None):
    ap = argparse.ArgumentParser(description="DEEPoS A/B boot state")
    ap.add_argument("--state", required=True, help="directory with boot.json (DATA)")
    ap.add_argument("--max-attempts", type=int, default=MAX_ATTEMPTS)
    ap.add_argument("cmd", choices=["status", "decide", "begin", "good", "switch"])
    ap.add_argument("slot", nargs="?", choices=list(SLOTS))
    args = ap.parse_args(argv)

    st = load(args.state)

    if args.cmd == "status":
        pass
    elif args.cmd == "decide":
        print(decide(st))
        return 0
    elif args.cmd == "begin":
        st = begin_boot(st, args.max_attempts)
        save(args.state, st)
    elif args.cmd == "good":
        st = mark_good(st)
        save(args.state, st)
    elif args.cmd == "switch":
        if not args.slot:
            raise SystemExit("switch requires a slot: A or B")
        st = switch_slot(st, args.slot)
        save(args.state, st)

    print(json.dumps(st, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
