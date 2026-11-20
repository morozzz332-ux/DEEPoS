#!/usr/bin/env python3
"""DEEPoS settings: persistence in /data/config/settings.toml and sysfs apply.

Run inside the build image:  python3 tests/config_test.py
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
BIN = ROOT / "apps" / "launcher" / "launcher"

checks = 0
failures = []


def check(name, cond, detail=""):
    global checks
    checks += 1
    if not cond:
        failures.append(f"{name}{': ' + detail if detail else ''}")


def run(*args, cwd=None):
    return subprocess.run(
        [str(BIN), *args],
        capture_output=True,
        text=True,
        cwd=cwd or str(ROOT),
        check=False,
    )


def parse(text):
    out = {}
    for part in text.split():
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def main() -> int:
    if not BIN.exists():
        print(f"missing {BIN}; run make -C apps/launcher")
        return 1

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="deepos-cfg-"))
    try:
        cfg = tmp / "config" / "settings.toml"
        cfg.parent.mkdir(parents=True)

        # 1. defaults without a file: nothing is touched on the device
        r = run("--config", str(cfg), "--print-config")
        d = parse(r.stdout)
        check("defaults rc", r.returncode == 0)
        check("default brightness untouched", d.get("brightness") == "0", r.stdout)
        check("default volume untouched", d.get("volume") == "0")
        check("default profile balanced", d.get("profile") == "balanced", r.stdout)
        check("no file created by --print-config", not cfg.exists())

        # 2. set brightness and persist
        r = run("--config", str(cfg), "--set", "brightness=40")
        d = parse(r.stdout)
        check("set brightness rc", r.returncode == 0, r.stderr)
        check("set brightness value", d.get("brightness") == "40", r.stdout)
        check("file saved", cfg.exists())
        body = cfg.read_text(encoding="utf-8")
        check("brightness line written", "brightness = 40" in body, body)

        # 3. volume and profile persist together
        run("--config", str(cfg), "--set", "volume=55")
        run("--config", str(cfg), "--set", "profile=eco")
        r = run("--config", str(cfg), "--print-config")
        d = parse(r.stdout)
        check("persisted brightness", d.get("brightness") == "40", r.stdout)
        check("persisted volume", d.get("volume") == "55")
        check("persisted profile", d.get("profile") == "eco")
        body = cfg.read_text(encoding="utf-8")
        check("three keys on disk", body.count("=") >= 3, body)
        check("no tmp file left", not (tmp / "config" / "settings.toml.tmp").exists())

        # 4. invalid values are rejected and do not touch the file
        before = cfg.read_text(encoding="utf-8")
        r = run("--config", str(cfg), "--set", "brightness=150")
        check("reject brightness>100", r.returncode == 2, f"rc={r.returncode}")
        r = run("--config", str(cfg), "--set", "profile=turbo")
        check("reject unknown profile", r.returncode == 2)
        r = run("--config", str(cfg), "--set", "nonsense=1")
        check("reject unknown key", r.returncode == 2)
        check("file untouched after rejects", cfg.read_text(encoding="utf-8") == before)

        # 5. --apply writes sysfs backlight and the profile marker
        sysfs = tmp / "sys"
        (sysfs / "backlight" / "backlight").mkdir(parents=True)
        bl = sysfs / "backlight" / "backlight" / "brightness"
        bl.write_text("45\n", encoding="utf-8")
        data = tmp / "data"
        data.mkdir()
        cfg.write_text(
            "# hand written\nbrightness = 40\nvolume = 0\nprofile = eco\n",
            encoding="utf-8",
        )
        r = run("--config", str(cfg), "--data", str(data), "--sysfs", str(sysfs) + "/", "--apply")
        d = parse(r.stdout)
        check("apply rc", r.returncode == 0, r.stderr)
        check("apply reported 1 knob", d.get("applied") == "1", r.stdout)
        check("apply reported power unsupported",
              "power\tunsupported" in r.stdout, r.stdout)
        check("backlight written", bl.read_text(encoding="utf-8").strip() == "18",
              bl.read_text(encoding="utf-8"))
        marker = data / "cpu-profile"
        check("profile marker written", marker.exists())
        check("profile marker content", marker.read_text(encoding="utf-8").strip() == "eco")

        # 5b. one power handler: applied limits are read back from sysfs
        policy = sysfs / "devices" / "system" / "cpu" / "cpufreq" / "policy0"
        policy.mkdir(parents=True)
        (policy / "scaling_available_frequencies").write_text(
            "408000 816000 1008000 1296000 1416000 1512000\n", encoding="utf-8")
        (policy / "scaling_max_freq").write_text("1416000\n", encoding="utf-8")
        (policy / "scaling_min_freq").write_text("408000\n", encoding="utf-8")
        (policy / "scaling_cur_freq").write_text("1416000\n", encoding="utf-8")
        (policy / "scaling_governor").write_text("performance\n", encoding="utf-8")

        r = run("--config", str(cfg), "--data", str(data), "--sysfs", str(sysfs),
                "--set-power", "balanced")
        check("set-power rc", r.returncode == 0, r.stderr)
        check("set-power applied", "power\tapplied" in r.stdout, r.stdout)
        check("balanced limit", (policy / "scaling_max_freq").read_text().strip() == "1008000")
        check("set-power saved profile",
              "profile = balanced" in cfg.read_text(encoding="utf-8"))
        check("set-power marker", marker.read_text(encoding="utf-8").strip() == "balanced")

        r = run("--config", str(cfg), "--data", str(data), "--sysfs", str(sysfs),
                "--set-power", "max")
        check("max limit", (policy / "scaling_max_freq").read_text().strip() == "1296000")

        r = run("--config", str(cfg), "--data", str(data), "--sysfs", str(sysfs),
                "--print-power")
        check("print-power profile", "profile=max" in r.stdout, r.stdout)
        check("print-power limit", "cpu=408000..1296000" in r.stdout, r.stdout)
        check("print-power governor", "governor=performance" in r.stdout, r.stdout)

        r = run("--config", str(cfg), "--data", str(data), "--sysfs", str(sysfs),
                "--set-power", "turbo")
        check("reject unknown power profile", r.returncode == 2, f"rc={r.returncode}")

        # 6. malformed file is tolerated: valid keys survive, bad ones ignored
        bad = tmp / "bad.toml"
        bad.write_text("brightness = abc\nvolume = 33\nprofile = max\n", encoding="utf-8")
        r = run("--config", str(bad), "--print-config")
        d = parse(r.stdout)
        check("malformed file rc", r.returncode == 0, r.stderr)
        check("valid key kept", d.get("volume") == "33", r.stdout)
        check("valid profile kept", d.get("profile") == "max")
        check("bad value ignored", d.get("brightness") == "0", r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        print("FAIL  config")
        for f in failures:
            print("  -", f)
        return 1

    print("PASS  config: defaults, save/load, reject invalid, sysfs apply, malformed file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
