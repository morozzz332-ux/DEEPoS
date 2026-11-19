#!/usr/bin/env python3
"""Settings screen: pressing A on a value card cycles it, saves and applies.

Checks the real launcher binary, the real settings.toml on the DATA tree and
the profile file the modules read.
"""
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "apps/launcher/launcher"
failures = []


def check(name, ok, detail=""):
    if ok:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        failures.append(name)


def tree(tmp):
    roms = tmp / "roms"
    (roms / "md").mkdir(parents=True)
    (roms / "md" / "g0.md").write_text("rom")
    data = tmp / "data"
    (data / "config").mkdir(parents=True)
    (data / "config" / "settings.toml").write_text(
        "# DEEPoS settings\nbrightness = 20\nvolume = 20\nprofile = eco\n",
        encoding="utf-8")
    return roms, data


def run(roms, data, keys, *extra):
    cmd = [str(LAUNCHER), "--roms", str(roms), "--data", str(data),
           "--screen", "settings", "--keys", keys, *extra]
    return subprocess.run(cmd, capture_output=True, text=True)


def read_cfg(data):
    path = data / "config" / "settings.toml"
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values, path.read_text(encoding="utf-8")


def main():
    with tempfile.TemporaryDirectory() as name:
        tmp = pathlib.Path(name)
        roms, data = tree(tmp)

        p = run(roms, data, "RIGHT,RIGHT,A")
        values, text = read_cfg(data)
        check("display card cycles brightness", values.get("brightness") == "40",
              f"{values.get('brightness')!r} rc={p.returncode}")
        check("comment header survives the save", text.startswith("# DEEPoS settings"))
        check("no temp file left", not (data / "config" / "settings.toml.tmp").exists())

        p = run(roms, data, "DOWN,A")
        values, _ = read_cfg(data)
        check("sound card cycles volume", values.get("volume") == "40")

        p = run(roms, data, "DOWN,RIGHT,RIGHT,A")
        values, _ = read_cfg(data)
        check("power card cycles profile", values.get("profile") == "balanced")

        p = run(roms, data, "DOWN,RIGHT,RIGHT,A")
        values, _ = read_cfg(data)
        check("profile cycles eco -> balanced -> max", values.get("profile") == "max")

        p = run(roms, data, "A")
        values, _ = read_cfg(data)
        check("region card leaves the file alone",
              values.get("brightness") == "40" and p.returncode == 0)

        p = run(roms, data, "RIGHT,RIGHT,A", "--sysfs", str(tmp / "sys"))
        values, _ = read_cfg(data)
        check("missing sysfs still saves the value", values.get("brightness") == "60",
              f"{values.get('brightness')!r} rc={p.returncode}")
        check("profile file written next to modules",
              (data / "cpu-profile").is_file() and
              (data / "cpu-profile").read_text(encoding="utf-8").strip() == "max")

        p = run(roms, data, "RIGHT,RIGHT,A", "--config", str(tmp / "other.toml"))
        check("explicit --config is honoured",
              (tmp / "other.toml").is_file())

    if failures:
        print(f"\nFAIL  settings: {len(failures)} problem(s)")
        return 1
    print("PASS  settings: display/sound/power cards cycle and persist")
    return 0


if __name__ == "__main__":
    sys.exit(main())
