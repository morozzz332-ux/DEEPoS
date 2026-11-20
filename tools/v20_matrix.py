#!/usr/bin/env python3
"""Build and check the V20 acceptance matrix.

The 175-row registry required by K3 is the union of two real registries:

  board/r36s-v20/data/rom-folders.txt   folders the DEEPoS launcher scans
  donor es_systems.cfg                  folders the donor EmulationStation had

`bios` is a data folder, not a system, and is excluded. Every row then gets
the route that actually exists: a DEEPoS override, a donor launch command, or
the donor core as a proposal when only EmulationStation knew the system.

`--import` writes board/r36s-v20/data/systems.tsv from those files.
`--check` validates the committed registry against them.
`--write` renders docs/V20-MATRIX.md, joining measured rows from
board/r36s-v20/data/matrix-evidence.tsv.

Nothing here talks to the console: hardware statuses only come from
matrix-evidence.tsv written after a run on the device.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

DATA = os.path.join("board", "r36s-v20", "data")
FOLDERS = os.path.join(DATA, "rom-folders.txt")
EMULATORS = os.path.join(DATA, "emulators.toml")
SYSTEMS = os.path.join(DATA, "systems.tsv")
BIOS = os.path.join(DATA, "bios-required.tsv")
EVIDENCE = os.path.join(DATA, "matrix-evidence.tsv")

CHECKS = [
    "core_load",
    "stand",
    "menu",
    "video",
    "audio",
    "controls",
    "sticks",
    "volume",
    "fn_save",
    "exit",
    "sram",
    "exit_state",
    "resume",
    "reboot",
    "recovery",
    "performance",
]
STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_RUN", "NOT_APPLICABLE"}

# Entry -> the system it duplicates. Both rows stay in the matrix (K3 counts
# them), but formats are inherited and the report marks the duplicate.
ALIASES = {
    "a2600": "atari2600",
    "gbah": "gb",
    "gbav": "gba",
    "gbch": "gbc",
    "gbh": "gb",
    "genh": "genesis",
    "ggh": "gamegear",
    "nesh": "nes",
    "snesh": "snes",
    "megadrive-japan": "megadrive",
    "pspminis": "psp",
    "ndsiware": "nds",
    "snesmsu1": "snes",
    "satellaview": "snes",
    "sufami": "snes",
    "tg16cd": "turbografxcd",
    "megacd": "segacd",
    "ps1": "psx",
    "dc": "dreamcast",
    "md": "megadrive",
    "sfc": "snes",
    "pce": "pcengine",
    "tg16": "turbografx",
    "gg": "gamegear",
    "sms": "mastersystem",
    "vb": "virtualboy",
    "zx": "zxspectrum",
    "ws": "wonderswan",
    "wsw": "wonderswancolor",
    "colecovision": "coleco",
    "pico8": "pico",
    "pokemini": "pokemonmini",
    "tic-80": "tic80",
    "pc-9800": "pc98",
    "neocd": "neogeocd",
}

# Systems whose BIOS rows live under another key.
BIOS_ALIASES = {"megacd": "segacd", "tg16cd": "pcenginecd"}

RE_CORE = re.compile(r"/([A-Za-z0-9_.+-]+)_libretro\.so")
RE_RA_GAME = re.compile(r"/retroarch-game\.sh\s+([A-Za-z0-9_.+-]+)\s")
RE_RA = re.compile(r"(^|[\s/])retroarch(32)?(\s|$)")


@dataclass
class System:
    system: str
    folder: str
    name: str = ""
    visible: str = "no"
    runtime: str = "none"
    core: str = ""
    formats: str = ""
    bios: list[str] = field(default_factory=list)
    source: str = "none"
    alias_of: str = ""

    def route_note(self) -> str:
        if self.runtime == "none":
            return "нет"
        if self.runtime == "port":
            return "run-port.sh"
        if self.source == "es":
            return f"предложен ({self.core})"
        return self.core or "-"


def read_folders(root: str) -> list[str]:
    out: list[str] = []
    with open(os.path.join(root, FOLDERS), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(line)
    return out


def read_toml_commands(path: str) -> dict[str, str]:
    """Read the flat `name = "command"` list; the launcher parses it the same way."""
    out: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if value.startswith('"') and value.endswith('"') and len(value) >= 2:
                    value = value[1:-1]
                if key:
                    out[key] = value
    except FileNotFoundError:
        pass
    return out


def read_bios(path: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\r\n")
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 2 and parts[0].strip():
                    mode = parts[3].strip() if len(parts) > 3 else "required"
                    out.setdefault(parts[0].strip(), []).append(f"{parts[1].strip()} ({mode})")
    except FileNotFoundError:
        pass
    return out


@dataclass
class EsEntry:
    folder: str
    fullname: str
    formats: str
    core: str


def read_es(es_cfg: str) -> dict[str, EsEntry]:
    out: dict[str, EsEntry] = {}
    if not es_cfg or not os.path.exists(es_cfg):
        return out
    for node in ET.parse(es_cfg).getroot().findall("system"):
        path = (node.findtext("path") or "").strip().strip("/")
        folder = path.split("/")[-1]
        if not folder:
            continue
        exts: list[str] = []
        for ext in (node.findtext("extension") or "").split():
            low = ext.lower()
            if low not in exts:
                exts.append(low)
        command = node.findtext("command") or ""
        m = RE_CORE.search(command)
        out[folder] = EsEntry(
            folder=folder,
            fullname=(node.findtext("fullname") or node.findtext("name") or folder).strip(),
            formats=" ".join(exts),
            core=m.group(1) if m else "",
        )
    return out


def classify(cmd: str) -> tuple[str, str]:
    m = RE_RA_GAME.search(cmd)
    if m:
        return "retroarch", m.group(1)
    m = RE_CORE.search(cmd)
    if m:
        return "retroarch", m.group(1)
    if cmd.strip() == "/bin/sh %ROM%":
        return "port", ""
    if RE_RA.search(cmd):
        return "retroarch", ""
    return ("standalone", "") if cmd else ("none", "")


def build_registry(root: str, donor_emulators: str, es_cfg: str) -> list[System]:
    folders = [f for f in read_folders(root) if f != "bios"]
    visible = set(folders)
    deepos = read_toml_commands(os.path.join(root, EMULATORS))
    donor = read_toml_commands(donor_emulators) if donor_emulators else {}
    bios = read_bios(os.path.join(root, BIOS))
    es = read_es(es_cfg)

    entries = sorted((set(folders) | set(es)) - {"bios"})
    rows: list[System] = []
    for entry in entries:
        cmd = deepos.get(entry, donor.get(entry, ""))
        es_entry = es.get(entry)
        if entry == "ports":
            runtime, core = "port", ""
        else:
            runtime, core = classify(cmd)
        source = "none"
        if entry in deepos:
            source = "deepos"
        elif entry in donor:
            source = "donor"
        if source == "none" and es_entry and es_entry.core:
            # Only EmulationStation knew this system: record the core it used
            # as a proposal, never as an installed route.
            runtime, core, source = "retroarch", es_entry.core, "es"

        name = es_entry.fullname if es_entry else entry
        formats = es_entry.formats if es_entry else ""
        alias = ALIASES.get(entry, "")
        if not formats and alias and alias in es:
            formats = es[alias].formats
        bios_key = BIOS_ALIASES.get(entry, entry)
        rows.append(
            System(
                system=entry,
                folder=entry,
                name=name,
                visible="yes" if entry in visible else "no",
                runtime=runtime,
                core=core,
                formats=formats,
                bios=list(bios.get(bios_key, [])),
                source=source,
                alias_of=alias,
            )
        )
    return rows


def write_systems(path: str, rows: list[System]) -> None:
    lines = [
        "# Canonical V20 system registry. Generated by tools/v20_matrix.py --import.",
        "# Columns: system<TAB>folder<TAB>name<TAB>visible<TAB>runtime<TAB>core<TAB>formats<TAB>bios<TAB>source<TAB>alias_of",
        "# visible: yes (in rom-folders.txt) | no (donor EmulationStation only)",
        "# runtime: retroarch | port | standalone | none",
        "# source:  deepos (emulators.toml) | donor (systems.toml) | es (core proposed by es_systems.cfg) | none",
    ]
    for row in rows:
        fields = [
            row.system,
            row.folder,
            row.name,
            row.visible,
            row.runtime,
            row.core,
            row.formats,
            " ".join(row.bios),
            row.source,
            row.alias_of,
        ]
        lines.append("\t".join(f.replace("\t", " ") for f in fields))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def read_systems(path: str) -> list[System]:
    rows: list[System] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            while len(parts) < 10:
                parts.append("")
            rows.append(
                System(
                    system=parts[0],
                    folder=parts[1] or parts[0],
                    name=parts[2],
                    visible=parts[3],
                    runtime=parts[4],
                    core=parts[5],
                    formats=parts[6],
                    bios=parts[7].split() if parts[7] else [],
                    source=parts[8],
                    alias_of=parts[9],
                )
            )
    return rows


def read_evidence(path: str) -> dict[str, dict[str, tuple[str, str]]]:
    out: dict[str, dict[str, tuple[str, str]]] = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\r\n")
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                system, check, status = parts[0].strip(), parts[1].strip(), parts[2].strip()
                note = parts[3].strip() if len(parts) > 3 else ""
                if check not in CHECKS or status not in STATUSES:
                    continue
                out.setdefault(system, {})[check] = (status, note)
    except FileNotFoundError:
        pass
    return out


def library_counts(rom_root: str, rows: list[System]) -> dict[str, tuple[int, str]]:
    out: dict[str, tuple[int, str]] = {}
    if not rom_root or not os.path.isdir(rom_root):
        return out
    for row in rows:
        path = os.path.join(rom_root, row.folder)
        if not os.path.isdir(path):
            continue
        count = 0
        sample = ""
        for dirpath, _dirnames, filenames in os.walk(path):
            for name in filenames:
                if name.startswith("."):
                    continue
                count += 1
                if not sample:
                    sample = os.path.relpath(os.path.join(dirpath, name), rom_root)
        if count:
            out[row.system] = (count, sample)
    return out


def ports_list(ports_root: str) -> list[str]:
    out: list[str] = []
    if not ports_root or not os.path.isdir(ports_root):
        return out
    for name in sorted(os.listdir(ports_root)):
        path = os.path.join(ports_root, name)
        if not os.path.isdir(path):
            continue
        try:
            entries = os.listdir(path)
        except OSError:
            continue
        if any(e.endswith(".sh") for e in entries) or "port.json" in entries:
            out.append(name)
    return out


def check(root: str, rows: list[System], cores_dir: str) -> list[str]:
    errors: list[str] = []
    folders = {f for f in read_folders(root) if f != "bios"}
    if len(rows) != len({r.system for r in rows}):
        errors.append("registry has duplicate systems")
    missing = sorted(folders - {r.folder for r in rows})
    if missing:
        errors.append(f"registry misses folders: {', '.join(missing)}")
    deepos = read_toml_commands(os.path.join(root, EMULATORS))
    known = {r.system for r in rows}
    for key in sorted(set(deepos) - known):
        errors.append(f"emulators.toml maps unknown system: {key}")
    for row in rows:
        if row.runtime == "retroarch" and not row.core:
            errors.append(f"{row.system}: retroarch route without a core")
        if row.runtime == "none" and row.source != "none":
            errors.append(f"{row.system}: source {row.source} but runtime none")
        if row.visible not in ("yes", "no"):
            errors.append(f"{row.system}: bad visible flag {row.visible}")
    if cores_dir and os.path.isdir(cores_dir):
        available = {
            name[: -len("_libretro.so")]
            for name in os.listdir(cores_dir)
            if name.endswith("_libretro.so")
        }
        for row in rows:
            if row.runtime == "retroarch" and row.core and row.core not in available:
                errors.append(f"{row.system}: core {row.core} missing in {cores_dir}")
    return errors


def render(
    rows: list[System],
    evidence: dict[str, dict[str, tuple[str, str]]],
    counts: dict[str, tuple[int, str]],
    ports: list[str],
    version: str,
    notes: list[str],
) -> str:
    routed = [r for r in rows if r.runtime != "none"]
    unrouted = [r for r in rows if r.runtime == "none"]
    hidden = [r for r in rows if r.visible == "no"]
    hidden_with_games = [r for r in hidden if r.system in counts]
    out: list[str] = []
    out.append("# Матрица приёмки V20")
    out.append("")
    out.append("Сгенерировано `tools/v20_matrix.py`. Не редактировать вручную.")
    out.append("")
    out.append(f"- Версия прошивки: `{version}`")
    out.append(f"- Систем в реестре: **{len(rows)}** — объединение `rom-folders.txt` "
               f"и реестра донора без папки `bios`")
    out.append(f"- С установленным маршрутом: **{sum(1 for r in routed if r.source != 'es')}**")
    out.append(f"- Только предложен маршрут (ядро из ES): **{sum(1 for r in routed if r.source == 'es')}**")
    out.append(f"- Без маршрута: **{len(unrouted)}**")
    out.append(f"- Не видны лаунчеру (`нет папки`): **{len(hidden)}**, из них с играми: "
               f"**{len(hidden_with_games)}**")
    out.append(f"- Установленных портов: **{len(ports)}**")
    out.append("")
    if hidden_with_games:
        names = ", ".join(f"`{r.system}`" for r in sorted(hidden_with_games, key=lambda r: r.system))
        out.append(f"> Игры есть, но лаунчер их не увидит: {names}.")
        out.append("")
    if notes:
        out.append("## Замечания")
        out.append("")
        for note in notes:
            out.append(f"- {note}")
        out.append("")
    out.append("## Как читать статусы")
    out.append("")
    out.append("| Статус | Значение |")
    out.append("|---|---|")
    out.append("| PASS | проверено на V20, доказательство в `matrix-evidence.tsv` |")
    out.append("| FAIL | проверено, не работает; причина в колонке evidence |")
    out.append("| BLOCKED | нельзя проверить без конкретной зависимости |")
    out.append("| NOT_RUN | ещё не проверялось |")
    out.append("| NOT_APPLICABLE | для этого маршрута проверка не имеет смысла |")
    out.append("")
    out.append("Маршрут `предложен` значит, что ядро известно из `es_systems.cfg`, "
               "но в `emulators.toml`/`systems.toml` строки нет: запуск ещё не проверялся.")
    out.append("")
    out.append("## Реестр систем")
    out.append("")
    header = ["Система", "Видна", "Название", "Маршрут", "Ядро", "Форматы", "BIOS", "Игр"]
    out.append("| " + " | ".join(header) + " |")
    out.append("|" + "---|" * len(header))
    for row in rows:
        route = row.route_note()
        if row.source == "none":
            route = "BLOCKED"
        if row.alias_of:
            route = f"{route}, копия `{row.alias_of}`"
        count = str(counts[row.system][0]) if row.system in counts else "-"
        cells = [
            f"`{row.system}`",
            "да" if row.visible == "yes" else "**нет**",
            row.name.replace("|", "/"),
            route,
            f"`{row.core}`" if row.core else "-",
            row.formats or "-",
            "<br>".join(row.bios) if row.bios else "-",
            count,
        ]
        out.append("| " + " | ".join(cells) + " |")
    out.append("")
    out.append("## Проверки по маршрутам")
    out.append("")
    out.append("Колонки совпадают с `matrix-evidence.tsv`; пустая ячейка — `NOT_RUN`.")
    out.append("")
    head = ["Система", "Ядро"] + CHECKS
    out.append("| " + " | ".join(head) + " |")
    out.append("|" + "---|" * len(head))
    for row in routed:
        ev = evidence.get(row.system, {})
        cells = [f"`{row.system}`", f"`{row.core}`" if row.core else "-"]
        for check in CHECKS:
            status, _note = ev.get(check, ("NOT_RUN", ""))
            cells.append("" if status == "NOT_RUN" else status)
        out.append("| " + " | ".join(cells) + " |")
    out.append("")
    out.append("## Без маршрута")
    out.append("")
    out.append("| Система | Видна | Тип | Что нужно |")
    out.append("|---|---|---|---|")
    routed_ids = {r.system for r in routed}
    for row in unrouted:
        base = ALIASES.get(row.system, "")
        if base and base in routed_ids:
            kind = f"алиас `{base}`"
            need = f"строку `{row.system}` в `emulators.toml` на ядро `{next(r.core for r in routed if r.system == base)}`"
        elif row.visible == "no":
            kind = "нет папки"
            need = "папку в `rom-folders.txt` и отдельный рантайм"
        else:
            kind = "отдельный рантайм"
            need = "команду запуска в `emulators.toml`"
        out.append(f"| `{row.system}` | {'да' if row.visible == 'yes' else 'нет'} | {kind} | {need} |")
    out.append("")
    out.append("## Порты")
    out.append("")
    if ports:
        for name in ports:
            out.append(f"- `{name}`")
    else:
        out.append("Порты не переданы (`--ports`).")
    out.append("")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="repository root")
    ap.add_argument("--import", dest="do_import", action="store_true",
                    help="write systems.tsv from --donor-dir and --es-cfg")
    ap.add_argument("--donor-dir", default="",
                    help="donor extra-emulators dir with systems.toml/cores.tsv")
    ap.add_argument("--es-cfg", default="", help="donor es_systems.cfg")
    ap.add_argument("--check", action="store_true", help="validate the registry")
    ap.add_argument("--write", default="", help="write the rendered matrix here")
    ap.add_argument("--roms", default="", help="ROM root for the library inventory")
    ap.add_argument("--ports", default="", help="installed ports directory")
    ap.add_argument("--cores", default="", help="directory with *_libretro.so to verify cores")
    ap.add_argument("--version", default="", help="firmware version shown in the report")
    args = ap.parse_args(argv)

    root = args.root
    if args.do_import:
        if not args.donor_dir:
            print("--import needs --donor-dir", file=sys.stderr)
            return 2
        rows = build_registry(root, os.path.join(args.donor_dir, "systems.toml"), args.es_cfg)
        write_systems(os.path.join(root, SYSTEMS), rows)
        routed = sum(1 for r in rows if r.runtime != "none")
        print(f"wrote {SYSTEMS}: {len(rows)} systems ({routed} routed, "
              f"{sum(1 for r in rows if r.visible == 'no')} launcher-invisible)")
        return 0

    systems_path = os.path.join(root, SYSTEMS)
    if not os.path.exists(systems_path):
        print(f"{SYSTEMS} missing; run --import first", file=sys.stderr)
        return 2
    rows = read_systems(systems_path)

    if args.check:
        errors = check(root, rows, args.cores)
        if errors:
            for err in errors:
                print(f"ERROR: {err}", file=sys.stderr)
            return 1
        print(f"matrix registry OK: {len(rows)} systems, "
              f"{sum(1 for r in rows if r.runtime != 'none')} routed")
        return 0

    if not args.write:
        ap.error("nothing to do: pass --check, --import or --write")

    version = args.version
    if not version:
        try:
            with open(os.path.join(root, "VERSION"), encoding="utf-8") as fh:
                version = fh.read().strip()
        except FileNotFoundError:
            version = "unknown"
    notes: list[str] = []
    if not args.es_cfg or not os.path.exists(args.es_cfg):
        notes.append("Форматы и предложенные маршруты не загружены: не передан существующий `--es-cfg`.")
    evidence = read_evidence(os.path.join(root, EVIDENCE))
    counts = library_counts(args.roms, rows)
    ports = ports_list(args.ports)
    text = render(rows, evidence, counts, ports, version, notes)
    out_path = os.path.join(root, args.write)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"wrote {args.write}: {len(rows)} systems, {len(evidence)} with evidence, "
          f"{len(counts)} with library rows, {len(ports)} ports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
