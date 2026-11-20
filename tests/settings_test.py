#!/usr/bin/env python3
"""Settings screen: pressing A on a value card cycles it, saves and applies.

Checks the real launcher binary, the real settings.toml on the DATA tree and
the profile file the modules read.
"""
import datetime
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

def test_themes(tmp, roms, data):
    into_themes = "DOWN,DOWN,DOWN,DOWN,DOWN,A"
    config = data / "config/settings.toml"
    run(roms, data, into_themes + ",DOWN,A,B")
    check("theme preview leaves persisted settings untouched", "theme" not in read_cfg(data)[0])
    run(roms, data, into_themes + ",DOWN,A,A")
    check("confirmation persists the new stock theme", read_cfg(data)[0].get("theme") == "zone")

    themes = roms / "themes"
    themes.mkdir()
    (themes / "custom.theme").write_text(
        "format=1\nlayout=split\nbackground=0c0e11\npanel=18202c\ntext=f8fafc\naccent=90d3ff\n")
    def render(theme, name):
        config.write_text(f"theme = {theme}\n")
        target = tmp / f"{name}.ppm"
        p = subprocess.run([str(LAUNCHER), "--roms", str(roms), "--data", str(data),
                            "--screen", "systems", "--out", str(target)],
                           capture_output=True, check=True)
        return target.read_bytes(), p.stderr

    terminal, _ = render("terminal", "terminal")
    zone, _ = render("zone", "zone")
    garage, _ = render("garage", "garage")
    custom, _ = render("user.custom", "custom")
    check("three stock variants use distinct screen rendering", len({terminal, zone, garage}) == 3)
    check("valid user theme changes the rendered screen", custom not in {terminal, zone, garage})
    (themes / "escape.theme").symlink_to(themes / "custom.theme")
    (themes / "broken.theme").write_text("format=1\nlayout=../../x\n" + "x" * 5000)
    for bad in ("user.missing", "user.escape", "user.broken"):
        frame, _ = render(bad, bad)
        check(f"{bad} falls back to the terminal", frame == terminal)
    config.write_text("theme = zone\n")
    run(roms, data, into_themes + ",select+start")
    check("physical chord restores the terminal from Appearance", read_cfg(data)[0].get("theme", "terminal") == "terminal")


def main():
    with tempfile.TemporaryDirectory() as name:
        tmp = pathlib.Path(name)
        roms, data = tree(tmp)
        test_themes(tmp, roms, data)
        (data / "config/settings.toml").write_text("brightness = 20\nvolume = 20\nprofile = eco\n")

        p = run(roms, data, "RIGHT,RIGHT,A")
        values, text = read_cfg(data)
        check("display card cycles brightness", values.get("brightness") == "40",
              f"{values.get('brightness')!r} rc={p.returncode}")
        check("comment header survives the save", text.startswith("# DEEPoS settings"))
        check("no temp file left", not (data / "config" / "settings.toml.tmp").exists())

        p = run(roms, data, "DOWN,A")
        values, _ = read_cfg(data)
        check("sound card cycles volume", values.get("volume") == "40")

        mixer_sys = tmp / "mixer"
        mixer = mixer_sys / "class/sound/card0/controlC0/volume_percent"
        mixer.parent.mkdir(parents=True)
        mixer.write_text("40\n")
        frame = tmp / "volume.ppm"
        p = run(roms, data, "VOL+,VOL-", "--sysfs", str(mixer_sys), "--out", str(frame))
        check("side volume keys apply to the mixer and persist",
              p.returncode == 0 and read_cfg(data)[0].get("volume") == "40" and
              mixer.read_text().strip() == "40")
        before = frame.read_bytes()
        run(roms, data, "VOL+", "--sysfs", str(mixer_sys), "--out", str(frame))
        check("the volume indicator changes with actual mixer level",
              mixer.read_text().strip() == "45" and frame.read_bytes() != before)

        p = run(roms, data, "DOWN,RIGHT,RIGHT,A")
        values, _ = read_cfg(data)
        check("power card cycles profile", values.get("profile") == "balanced")

        p = run(roms, data, "DOWN,RIGHT,RIGHT,A")
        values, _ = read_cfg(data)
        check("profile cycles eco -> balanced -> max", values.get("profile") == "max")

        p = run(roms, data, "A")
        values, _ = read_cfg(data)
        check("menu tones can be disabled without changing brightness",
              values.get("menu_sounds") == "off" and values.get("brightness") == "40" and p.returncode == 0)

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

        p = run(roms, data, "DOWN,DOWN,RIGHT,A")
        check("modules shortcut opens the modules tab", "screen=modules" in p.stdout)
        p = run(roms, data, "DOWN,DOWN,RIGHT,A,B")
        check("back returns to the settings shortcut", "screen=settings level=0 sel=7" in p.stdout)

        policy = tmp / "sys/devices/system/cpu/cpufreq/policy0"
        policy.mkdir(parents=True)
        (policy / "scaling_available_frequencies").write_text("408000 816000 1008000 1416000 1512000\n")
        (policy / "scaling_max_freq").write_text("1416000\n")
        (policy / "scaling_min_freq").write_text("408000\n")
        p = run(roms, data, "DOWN,RIGHT,RIGHT,A", "--sysfs", str(tmp / "sys"))
        check("eco applies the hardware CPU cap", (policy / "scaling_max_freq").read_text().strip() == "816000")

        run(roms, data, "DOWN,DOWN,A,RIGHT,RIGHT,A,DOWN,A")
        result = subprocess.run([str(LAUNCHER), "--data", str(data), "--print-retroarch-config"],
                                check=True, text=True, capture_output=True)
        check("RetroArch launch override passes the three selected preferences",
              set(result.stdout.splitlines()) == {'video_smooth = "true"',
                  'fps_show = "true"', 'video_scale_integer = "true"'}, result.stdout)

        clock = data / "config" / "clock"
        february = datetime.datetime(2024, 2, 29, 12, tzinfo=datetime.timezone.utc)
        clock.write_text(f"UTC {int(february.timestamp())}\n")
        p = run(roms, data, "DOWN,DOWN,DOWN,DOWN,RIGHT,A,DOWN,DOWN,A")
        check("region list saves the named time zone with the same UTC timestamp",
              p.returncode == 0 and clock.read_text() ==
              f"Europe/Moscow {int(february.timestamp())}\n")
        p = run(roms, data, "DOWN,DOWN,DOWN,DOWN,A,RIGHT,DOWN,A")
        january = february.replace(month=1)
        check("date editor changes the month and saves the corresponding UTC timestamp",
              p.returncode == 0 and clock.read_text() ==
              f"Europe/Moscow {int(january.timestamp())}\n")
        run(roms, data, "DOWN,DOWN,DOWN,DOWN,A,UP,B")
        check("B discards the date draft",
              clock.read_text() == f"Europe/Moscow {int(january.timestamp())}\n")

        cores = data / "emus" / "cores"
        cores.mkdir(parents=True)
        (cores / "genesis_plus_gx_libretro.so").touch()
        (cores / "picodrive_libretro.so").touch()
        (cores.parent / "cores.tsv").write_text("md\tgenesis_plus_gx absent picodrive\n")
        emulators = tmp / "emulators.toml"
        emulators.write_text('md = "/usr/local/bin/retroarch-game.sh genesis_plus_gx %ROM%"\n')
        select = ("--screen", "systems", "--emulators", str(emulators))
        pick = data / "config" / "core-md"
        p = run(roms, data, "X,DOWN,DOWN,A", *select)
        check("core picker lists installed cores and saves the selected one",
              p.returncode == 0 and pick.exists() and pick.read_text() == "picodrive\n")
        run(roms, data, "X,UP,B", *select)
        check("cancel leaves the selected core unchanged",
              pick.exists() and pick.read_text() == "picodrive\n")
        run(roms, data, "X,UP,UP,A", *select)
        check("Auto restores the default core", not pick.exists())

    if failures:
        print(f"\nFAIL  settings: {len(failures)} problem(s)")
        return 1
    print("PASS  settings: display/sound/power cards cycle and persist")
    return 0


if __name__ == "__main__":
    sys.exit(main())
