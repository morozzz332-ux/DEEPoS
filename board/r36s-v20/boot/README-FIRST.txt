DEEPoS - where to put your games
================================

This small FAT volume is the BOOT partition. The launcher itself lives in
DEEPOS_A / DEEPOS_B, your settings and save states live in DATA, and games go
to ROMS (the big one that Windows shows as a normal drive).

Layout of the ROMS volume:

    ROMS/
      md/            Mega Drive / Genesis      (*.md, *.bin, *.gen, *.smd)
      snes/          Super Nintendo             (*.sfc, *.smc)
      nes/           NES                        (*.nes)
      gb/ gbc/ gba/  Game Boy family            (*.gb, *.gbc, *.gba)
      psx/           PlayStation                (*.cue + *.bin, *.chd)
      psp/           PSP                        (*.iso, *.cso)
      n64/           Nintendo 64                (*.z64, *.n64, *.v64)
      dc/            Dreamcast                  (*.chd, *.gdi, *.cdi)
      ports/         native ports and PortMaster games (*.sh + its folder)
      bios/          console BIOS files, if an emulator asks for them

Folder names are lowercase and must match the emulator table
(/data/emulators.toml). Copy whole folders from your backup - the launcher
rescans the volume on every start.

First boot writes a small report to BOOT/report/ (checks.txt and dmesg.txt).
If the screen stays black, pull the card and read BOOT/report/checks.txt:
"verdict=FAIL" means the panel or the DATA partition did not come up.

Settings live in DATA/config/settings.toml (brightness, volume, cpu profile).
Save states live in DATA/saves/<system>/<game>/slotN.state.
